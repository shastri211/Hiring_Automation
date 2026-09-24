import os
import logging
import secrets
import aiofiles
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.db.session import get_db
from app.models.job import Job
from app.models.batch import ScreeningBatch
from app.models.resume import Resume
from app.models.profile import CandidateProfile
from app.models.screening import ScreeningResult
from app.models.interview import Interview
from app.models.application import Application, ApplicationResumeHistory
from app.models.decision_audit import DecisionAudit
from app.models.email import EmailMessage
from app.models.talent_pool import TalentPoolEntry
from app.models.candidate import CandidateMatchSuggestion
from app.models.public_application import PublicApplicationSubmission
from app.schemas.job import JobCreate, JobResponse
from app.schemas.public_application import SelfReportedContact
from app.schemas.screening import (
    ScreeningResultResponse,
    PaginatedScreeningResultResponse,
    CandidateDetailResponse,
    CandidateProfileDetail,
    BatchProgressResponse,
    BatchProgressDetail,
    DecisionUpdate,
    BulkDecisionUpdate,
    InterviewResponse,
    JobBatchOverviewItem,
    is_evaluation_failed,
)
from app.services.screener import screener_service
from app.services.profiler import profiler_service
from app.services.embeddings import embedding_router
from app.services.queue import queue_service
from app.services.extractor.factory import get_extractor
from app.services.vector_store import vector_store
from app.services.model_registry import model_registry
from app.services.outreach import outreach_service
from app.services.interview import interview_adapter
from app.services.dograh import dograh_client
from app.services.storage import sanitize_filename
from app.services import screening_trigger
from app.services import tenancy
from app.services import screening_audit
from app.services.candidate_directory import get_candidate_summaries
from app.api.deps import get_current_user
from app.models.user import User
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/", response_model=List[JobResponse])
async def list_jobs(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(
        select(Job).where(Job.organization_id == current_user.organization_id).order_by(Job.id.desc())
    )
    return result.scalars().all()


# -- cross-job processing overview (sidebar > Processing) ----------------------
# Registered before the "/{job_id}" routes below so "/batches/overview" isn't
# swallowed by the int path-converter on job_id.

@router.get("/batches/overview", response_model=List[JobBatchOverviewItem])
async def get_batches_overview(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(
        select(ScreeningBatch, Job.title, Job.status)
        .join(Job, Job.id == ScreeningBatch.job_id)
        .where(Job.organization_id == current_user.organization_id)
        .order_by(ScreeningBatch.created_at.desc())
        .limit(100)
    )
    rows = result.all()

    # total_resumes/processed/failed on ScreeningBatch are snapshots updated
    # incrementally as resumes are processed (see
    # orchestrator.update_batch_progress) - they never get corrected if a
    # resume is later deleted out from under a batch (no such "delete a
    # resume" feature exists yet, but it has happened via direct DB
    # intervention), leaving a batch permanently showing candidates that no
    # longer exist. Computed live from Resume instead, in one grouped query
    # covering every batch on this page rather than one query per batch.
    batch_ids = [batch.id for batch, _, _ in rows]
    counts_by_batch: dict[int, dict[str, int]] = {}
    if batch_ids:
        count_rows = await db.execute(
            select(Resume.batch_id, Resume.status, func.count(Resume.id))
            .where(Resume.batch_id.in_(batch_ids))
            .group_by(Resume.batch_id, Resume.status)
        )
        for batch_id, status_value, count in count_rows.all():
            counts_by_batch.setdefault(batch_id, {})[status_value] = count

    items = []
    for batch, job_title, job_status in rows:
        status_counts = counts_by_batch.get(batch.id, {})
        # A SCREEN batch never has Resume rows pointing at its batch_id (see
        # screening_trigger.enqueue_screen_job) - its total_resumes is
        # assigned directly there and stays meaningful. Only an UPLOAD batch
        # gets its total recomputed live, since it's the one whose
        # total_resumes can go stale (a resume deleted after upload leaves
        # the snapshot pointing at candidates that no longer exist).
        # A SCREEN batch has no Resume rows pointing at its batch_id (see
        # screening_trigger.enqueue_screen_job), so status_counts is always
        # empty for one - processed/failed have to come from the batch's own
        # snapshot columns (kept correct by the worker's screen_job handling)
        # instead, the same way total already does below.
        if batch.batch_type == "SCREEN":
            total = batch.total_resumes
            processed = batch.processed
            failed = batch.failed
        else:
            total = sum(status_counts.values())
            processed = status_counts.get("READY", 0)
            failed = status_counts.get("FAILED", 0)
        items.append(
            JobBatchOverviewItem(
                job_id=batch.job_id,
                job_title=job_title,
                job_status=job_status,
                batch_id=batch.id,
                batch_status=batch.status,
                total=total,
                processed=processed,
                failed=failed,
                created_at=batch.created_at,
                batch_type=batch.batch_type,
            )
        )
    return items



# -- helpers -------------------------------------------------------------------

async def _get_job_or_404(job_id: int, db: AsyncSession, organization_id: int) -> Job:
    """The job, only within the caller's organization - another
    organization's job 404s exactly like a missing one. Every /{job_id}/...
    route resolves its job here first and anchors all child queries
    (resumes, results, interviews, batches) on that job_id."""
    return await tenancy.get_job_for_org_or_404(db, job_id, organization_id)


def _safe_error_message(resume: Resume) -> Optional[str]:
    """Never surface raw extractor/LLM/DB exception text to the frontend -
    resume.error_message can contain internal details (file paths, library
    internals, provider error bodies). Log the raw message server-side where
    it's set (orchestrator.py) and only expose this generic string here."""
    if not resume.error_message:
        return None
    return "Processing failed - file may be corrupted or unsupported."


def _fallback_job_profile(job: Job) -> dict:
    return {
        "title": job.title,
        "role_summary": job.description,
        "required_skills": [],
        "preferred_skills": [],
        "minimum_experience_years": 0,
        "education_requirements": None,
        "responsibilities": [],
        "requirements": []
    }


# Fields considered "meaningful" for a job profile - mirrors
# orchestrator._is_valid_profile's intent for candidate profiles. A profile
# is valid if any of these carries real content; otherwise it's a
# technically-truthy but useless dict (e.g. an LLM response with every field
# empty/null) and should be treated the same as a profiling failure.
_JOB_PROFILE_MEANINGFUL_FIELDS = ("role_summary", "required_skills", "preferred_skills", "responsibilities", "requirements")


def _is_valid_job_profile(job_profile: dict) -> bool:
    if not isinstance(job_profile, dict) or not job_profile:
        return False
    return any(job_profile.get(field) for field in _JOB_PROFILE_MEANINGFUL_FIELDS)


async def _bootstrap_job_profile_and_embedding(job: Job) -> None:
    """Populates job.job_profile, job.embedding_profile and job.embedding_status.

    Falls back to a minimal profile if LLM profiling is unavailable or
    returns a well-formed-but-empty result, and marks the embedding as
    FAILED (rather than leaving the READY default) if no embedding provider
    is currently eligible.
    """
    try:
        job_profile = await profiler_service.profile_job(job.description)
        if not _is_valid_job_profile(job_profile):
            job_profile = _fallback_job_profile(job)
    except Exception as e:
        logger.warning(f"Job profiling failed for job {job.id}, using fallback profile: {e}")
        job_profile = _fallback_job_profile(job)

    job.job_profile = job_profile

    try:
        # The embedding itself is not persisted (jobs are not stored as vectors in
        # Qdrant); this call only validates that an embedding profile is currently
        # eligible and pins job.embedding_profile so the screener later re-embeds
        # with the same profile.
        _embedding, profile = await embedding_router.generate_embedding(str(job_profile))
        job.embedding_profile = profile.model
        job.embedding_status = "READY"
    except Exception as e:
        logger.error(f"Embedding profile selection failed for job {job.id}: {e}")
        job.embedding_profile = None
        job.embedding_status = "FAILED"


# -- create job ----------------------------------------------------------------

MIN_JOB_DESCRIPTION_LENGTH = 15


def _require_meaningful_description(description: str) -> None:
    """Guards against an empty/near-empty JD reaching profiling and
    screening as a "valid" job - profiling would otherwise either raise
    (caught and silently downgraded to a near-useless fallback profile, see
    _bootstrap_job_profile_and_embedding) or, worse, return a technically
    well-formed but meaningless profile."""
    if len((description or "").strip()) < MIN_JOB_DESCRIPTION_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Job description must be at least {MIN_JOB_DESCRIPTION_LENGTH} characters.",
        )


@router.post("/", response_model=JobResponse, status_code=201)
async def create_job(
    job_in: JobCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_meaningful_description(job_in.description)
    job = Job(title=job_in.title, description=job_in.description, organization_id=current_user.organization_id)
    db.add(job)
    await db.flush()

    await _bootstrap_job_profile_and_embedding(job)

    await db.commit()
    await db.refresh(job)
    return job

@router.post("/upload", response_model=JobResponse, status_code=201)
async def upload_job(
    title: str = Form(...),
    description: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not description and not file:
        raise HTTPException(status_code=400, detail="Must provide either a description or a file")
        
    extracted_text = ""
    
    if file:
        from app.api.resumes import ALLOWED_CONTENT_TYPES, ALLOWED_EXTENSIONS, MAX_RESUME_FILE_SIZE_BYTES

        ext = os.path.splitext(file.filename or "")[1].lower()
        if file.content_type not in ALLOWED_CONTENT_TYPES or ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail="Job description file must be a .pdf or .docx.")

        content = await file.read()
        if len(content) == 0 or len(content) > MAX_RESUME_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"Job description file must be non-empty and under {settings.MAX_RESUME_FILE_SIZE_MB}MB.",
            )

        os.makedirs("uploads/jobs", exist_ok=True)
        file_path = os.path.join("uploads/jobs", sanitize_filename(file.filename))
        async with aiofiles.open(file_path, 'wb') as out_file:
            await out_file.write(content)

        try:
            extractor = get_extractor(file_path, file.content_type)
            extracted_text = await extractor.extract(file_path)
        except Exception as e:
            try:
                os.remove(file_path)
            except OSError:
                pass
            raise HTTPException(status_code=400, detail=f"Failed to parse JD file: {str(e)}")
            
    # Converge paths
    final_description = ""
    if description:
        final_description += description + "\n\n"
    if extracted_text:
        final_description += extracted_text

    _require_meaningful_description(final_description)

    # Re-use existing Job Create logic pipeline
    job = Job(title=title, description=final_description, organization_id=current_user.organization_id)
    db.add(job)
    await db.flush()

    await _bootstrap_job_profile_and_embedding(job)

    await db.commit()
    await db.refresh(job)
    return job

# -- get job -------------------------------------------------------------------

@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    return await _get_job_or_404(job_id, db, current_user.organization_id)


@router.post("/{job_id}/pause", response_model=JobResponse)
async def pause_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = await _get_job_or_404(job_id, db, current_user.organization_id)
    if job.status == "ACTIVE":
        job.status = "PAUSED"
        await db.commit()
        await db.refresh(job)
    return job


@router.post("/{job_id}/resume", response_model=JobResponse)
async def resume_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = await _get_job_or_404(job_id, db, current_user.organization_id)
    if job.status == "PAUSED":
        job.status = "ACTIVE"
        await db.commit()
        await db.refresh(job)

        # Bug fix: while this job was paused, orchestrator.process_candidate
        # (app/services/orchestrator.py) drops any in-flight resume for it
        # back to UPLOADED and returns without raising - which means the
        # worker acks and permanently discards that queue message (no
        # exception was raised, so app/worker.py treats it as a completed
        # task). Nothing was re-enqueuing those resumes on resume, so they
        # sat in UPLOADED forever with no further action. Re-enqueue them
        # here so pausing a job can never silently and permanently drop a
        # resume out of the pipeline.
        stuck_res = await db.execute(
            select(Resume).where(Resume.job_id == job_id, Resume.status == "UPLOADED")
        )
        stuck_resumes = stuck_res.scalars().all()
        for r in stuck_resumes:
            await queue_service.enqueue_resume(r.id, job_id=job_id, batch_id=r.batch_id)
        if stuck_resumes:
            logger.info(
                f"Resumed job {job_id}: re-enqueued {len(stuck_resumes)} resume(s) "
                f"left stuck in UPLOADED status by the pause."
            )
    return job


@router.post("/{job_id}/archive", response_model=JobResponse)
async def archive_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = await _get_job_or_404(job_id, db, current_user.organization_id)
    if job.status != "ARCHIVED":
        job.status = "ARCHIVED"
        await db.commit()
        await db.refresh(job)
    return job


# -- public application link (candidate-initiated applications) ----------------
# The token is the link's only credential (see app/api/public_application.py).
# Closing clears it and rotating replaces it, so an old link stops resolving.

@router.post("/{job_id}/application-link", response_model=JobResponse)
async def open_application_link(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = await _get_job_or_404(job_id, db, current_user.organization_id)
    if not job.application_token:
        job.application_token = secrets.token_urlsafe(32)
        await db.commit()
        await db.refresh(job)
    return job


@router.post("/{job_id}/application-link/rotate", response_model=JobResponse)
async def rotate_application_link(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = await _get_job_or_404(job_id, db, current_user.organization_id)
    job.application_token = secrets.token_urlsafe(32)
    await db.commit()
    await db.refresh(job)
    return job


@router.delete("/{job_id}/application-link", response_model=JobResponse)
async def close_application_link(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = await _get_job_or_404(job_id, db, current_user.organization_id)
    if job.application_token:
        job.application_token = None
        await db.commit()
        await db.refresh(job)
    return job


@router.delete("/{job_id}", status_code=204)
async def delete_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = await _get_job_or_404(job_id, db, current_user.organization_id)
    
    # Clean up Qdrant vectors
    if job.embedding_profile:
        profile = model_registry.get_profile_by_model(job.embedding_profile)
        if profile:
            try:
                await vector_store.delete_points_by_filter(profile.collection, {"job_id": job.id})
            except Exception as e:
                logger.error(f"Failed to delete Qdrant vectors for job {job.id} in collection {profile.collection}: {e}")
        else:
            logger.warning(f"No embedding profile registered for '{job.embedding_profile}'; skipping Qdrant cleanup for job {job.id}")

    # Delete files associated with this job. Resumes are stored by
    # storage_service under "{STORAGE_LOCAL_DIR}/job_{job_id}/batch_.../..."
    # (see app/api/resumes.py + app/services/storage.py) - must match that
    # layout exactly or the on-disk files are silently orphaned.
    import shutil
    job_dir = os.path.join(settings.STORAGE_LOCAL_DIR, f"job_{job_id}")
    if os.path.exists(job_dir):
        shutil.rmtree(job_dir, ignore_errors=True)

    # Delete from DB (manual cascade to avoid FK constraint errors). Order
    # matters: every table below is deleted before the row(s) it references,
    # working from the leaves of the FK graph up to Job itself. Application
    # and its dependents (DecisionAudit, ApplicationResumeHistory) are the
    # ones most recently added and are the reason DELETE /jobs/{id} used to
    # fail with "applications_current_resume_id_fkey" - Resume can't be
    # deleted while an Application still points at it.
    from sqlalchemy import delete, update
    resume_ids_subq = select(Resume.id).where(Resume.job_id == job_id)
    application_ids_subq = select(Application.id).where(Application.job_id == job_id)

    await db.execute(delete(DecisionAudit).where(DecisionAudit.application_id.in_(application_ids_subq)))
    await db.execute(delete(ScreeningResult).where(ScreeningResult.job_id == job_id))
    await db.execute(delete(EmailMessage).where(EmailMessage.job_id == job_id))
    # A talent-pool entry whose own resume belongs to this job is deleted
    # (the resume it points at is about to be destroyed below). One whose
    # resume belongs to a DIFFERENT, surviving job but was merely added
    # while viewing this job (added_from_job_id) keeps existing - only that
    # informational pointer is cleared, mirroring the *_email_template_id
    # FKs' ondelete="SET NULL" - deleting the whole entry here would
    # silently destroy curated tags/notes for a candidate this job's
    # deletion has nothing to do with.
    await db.execute(delete(TalentPoolEntry).where(TalentPoolEntry.resume_id.in_(resume_ids_subq)))
    await db.execute(
        update(TalentPoolEntry)
        .where(TalentPoolEntry.added_from_job_id == job_id)
        .values(added_from_job_id=None)
    )
    await db.execute(delete(CandidateMatchSuggestion).where(CandidateMatchSuggestion.resume_id.in_(resume_ids_subq)))
    await db.execute(delete(ApplicationResumeHistory).where(
        ApplicationResumeHistory.application_id.in_(application_ids_subq)
        | ApplicationResumeHistory.resume_id.in_(resume_ids_subq)
    ))
    await db.execute(delete(Application).where(Application.job_id == job_id))
    await db.execute(delete(CandidateProfile).where(CandidateProfile.resume_id.in_(resume_ids_subq)))
    await db.execute(delete(PublicApplicationSubmission).where(PublicApplicationSubmission.job_id == job_id))
    await db.execute(delete(Interview).where(Interview.job_id == job_id))
    await db.execute(delete(Resume).where(Resume.job_id == job_id))
    await db.execute(delete(ScreeningBatch).where(ScreeningBatch.job_id == job_id))

    await db.delete(job)
    await db.commit()
    
    return None


# -- trigger screening ---------------------------------------------------------

@router.post("/{job_id}/screen", status_code=202)
async def trigger_screening(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_job_or_404(job_id, db, current_user.organization_id)

    # total_resumes = candidates this run will actually attempt to screen, so
    # the cross-job Processing overview (/jobs/batches/overview) shows real
    # progress instead of a permanent 0/0/0 row for screening-trigger batches.
    try:
        batch = await screening_trigger.enqueue_screen_job(db, job_id)
    except Exception:
        logger.exception("Failed to enqueue screening for job %s", job_id)
        raise HTTPException(status_code=502, detail="Failed to enqueue screening - the queue may be unavailable. Try again shortly.")

    return {"message": "Screening batch created and enqueued", "batch_id": batch.id}


# -- manual embedding-profile migration (admin safety net; nothing currently --
# -- auto-detects a job's embedding profile going ineligible) -----------------

@router.post("/{job_id}/migrate-embedding-profile", status_code=202)
async def trigger_embedding_migration(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = await _get_job_or_404(job_id, db, current_user.organization_id)

    if job.embedding_status == "MIGRATING":
        raise HTTPException(status_code=409, detail="This job's embedding profile is already migrating.")

    try:
        await queue_service.enqueue_task({"action": "migrate_job", "job_id": job_id})
    except Exception:
        logger.exception("Failed to enqueue embedding migration for job %s", job_id)
        raise HTTPException(
            status_code=502,
            detail="Failed to enqueue migration - the queue may be unavailable. Try again shortly.",
        )

    return {"message": "Embedding profile migration enqueued"}


# -- paginated, filtered, sorted results ---------------------------------------

@router.get("/{job_id}/results", response_model=PaginatedScreeningResultResponse)
async def get_screening_results(
    job_id: int,
    decision: Optional[str] = Query(None, description="SHORTLIST | REVIEW | REJECT"),
    min_score: Optional[float] = Query(None, ge=0, le=100),
    max_score: Optional[float] = Query(None, ge=0, le=100),
    status: Optional[str] = Query(None, description="Resume status: UPLOADED|PROCESSING|READY|FAILED"),
    sort_by: str = Query("score", description="score | created_at"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_job_or_404(job_id, db, current_user.organization_id)

    query = (
        select(
            Resume,
            ScreeningResult,
        )
        .outerjoin(ScreeningResult, (ScreeningResult.resume_id == Resume.id) & (ScreeningResult.job_id == job_id))
        .where(Resume.job_id == job_id)
    )

    if decision:
        if decision.upper() == "NULL" or decision == "":
            query = query.where(ScreeningResult.decision.is_(None))
        else:
            query = query.where(ScreeningResult.decision == decision.upper())
    if min_score is not None:
        query = query.where(ScreeningResult.score >= min_score)
    if max_score is not None:
        query = query.where(ScreeningResult.score <= max_score)
    if status:
        query = query.where(Resume.status == status.upper())

    # Count total before pagination
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar_one()

    # Sorting
    if sort_by == "created_at":
        query = query.order_by(Resume.created_at.desc())
    else:
        query = query.order_by(ScreeningResult.score.desc().nulls_last())

    # Pagination
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    rows = result.all()

    # Phase 6: one batched candidate-identity resolution (display name,
    # canonical candidate_id, applications_count) covering every resume on
    # this page - not a lookup per row.
    summaries = await get_candidate_summaries(db, [row.Resume.id for row in rows])

    items = []
    for row in rows:
        resume = row.Resume
        sr = row.ScreeningResult
        summary = summaries.get(resume.id, {})

        if sr:
            items.append(ScreeningResultResponse(
                id=sr.id,
                job_id=job_id,
                resume_id=resume.id,
                score=sr.score,
                semantic_score=sr.semantic_score,
                strengths=sr.strengths,
                gaps=sr.gaps,
                evidence=sr.evidence,
                decision=sr.decision,
                notes=sr.notes,
                created_at=sr.created_at,
                status=resume.status,
                error_message=_safe_error_message(resume),
                display_name=summary.get("display_name"),
                candidate_id=summary.get("candidate_id"),
                applications_count=summary.get("applications_count"),
                evaluation_failed=is_evaluation_failed(sr.notes),
            ))
        else:
            items.append(ScreeningResultResponse(
                id=None,
                job_id=job_id,
                resume_id=resume.id,
                score=None,
                semantic_score=None,
                strengths=None,
                gaps=None,
                evidence=None,
                decision=None,
                notes=None,
                created_at=None,
                status=resume.status,
                error_message=_safe_error_message(resume),
                display_name=summary.get("display_name"),
                candidate_id=summary.get("candidate_id"),
                applications_count=summary.get("applications_count"),
            ))

    return PaginatedScreeningResultResponse(
        items=items, total=total, page=page, page_size=page_size
    )


# -- candidate detail ----------------------------------------------------------

@router.get("/{job_id}/results/{resume_id}", response_model=CandidateDetailResponse)
async def get_candidate_detail(
    job_id: int, resume_id: int, db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_job_or_404(job_id, db, current_user.organization_id)

    # Ownership check: resume must belong to this job
    resume_res = await db.execute(
        select(Resume).where(Resume.id == resume_id, Resume.job_id == job_id)
    )
    resume = resume_res.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found for this job")

    # Candidate profile (may not exist yet if still PROCESSING)
    profile_res = await db.execute(
        select(CandidateProfile).where(CandidateProfile.resume_id == resume_id)
    )
    profile = profile_res.scalar_one_or_none()

    # Screening result (may not exist yet)
    screening_res = await db.execute(
        select(ScreeningResult).where(
            ScreeningResult.resume_id == resume_id,
            ScreeningResult.job_id == job_id,  # ownership check
        )
    )
    screening = screening_res.scalar_one_or_none()

    profile_detail = None
    if profile:
        profile_detail = CandidateProfileDetail(
            name=profile.name,
            email=profile.email,
            phone=profile.phone,
            summary=profile.summary,
            total_experience_years=profile.total_experience_years,
            education=profile.education,
            experience=profile.experience,
            skills=profile.skills,
            projects=profile.projects,
            certifications=profile.certifications,
            languages=profile.languages,
            achievements=profile.achievements,
        )

    # Interview result (may not exist)
    interview_res = await db.execute(
        select(Interview).where(
            Interview.resume_id == resume_id,
            Interview.job_id == job_id,
        )
    )
    interview = interview_res.scalar_one_or_none()

    # Phase 6: centralized candidate-identity resolution (single resume, but
    # still through the shared batched function for one consistent chain).
    summary = (await get_candidate_summaries(db, [resume.id])).get(resume.id, {})

    screening_response = None
    if screening:
        screening_response = ScreeningResultResponse(
            id=screening.id,
            job_id=screening.job_id,
            resume_id=screening.resume_id,
            score=screening.score,
            semantic_score=screening.semantic_score,
            strengths=screening.strengths,
            gaps=screening.gaps,
            evidence=screening.evidence,
            decision=screening.decision,
            notes=screening.notes,
            created_at=screening.created_at,
            status=resume.status,
            error_message=_safe_error_message(resume),
            display_name=summary.get("display_name"),
            candidate_id=summary.get("candidate_id"),
            applications_count=summary.get("applications_count"),
            raw_candidate_id=resume.candidate_id,
            evaluation_failed=is_evaluation_failed(screening.notes),
        )

    submission = (
        await db.execute(
            select(PublicApplicationSubmission).where(PublicApplicationSubmission.resume_id == resume_id)
        )
    ).scalar_one_or_none()
    self_reported_contact = (
        SelfReportedContact(
            name=submission.applicant_name,
            email=submission.applicant_email,
            phone=submission.applicant_phone,
            submitted_at=submission.created_at,
        )
        if submission
        else None
    )

    return CandidateDetailResponse(
        resume_id=resume.id,
        filename=resume.filename,
        status=resume.status,
        error_message=_safe_error_message(resume),
        profile=profile_detail,
        screening=screening_response,
        interview=InterviewResponse.model_validate(interview) if interview else None,
        self_reported_contact=self_reported_contact,
    )


# -- manual Dograh resync (bounded safety net; webhooks aren't guaranteed --
# -- exactly-once-ever delivery) -----------------------------------------------

@router.post("/{job_id}/interviews/{resume_id}/resync", response_model=dict)
async def resync_interview(
    job_id: int,
    resume_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_job_or_404(job_id, db, current_user.organization_id)

    result = await db.execute(
        select(Interview).where(
            Interview.resume_id == resume_id,
            Interview.job_id == job_id,
        )
    )
    interview = result.scalar_one_or_none()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found for this candidate")

    if not interview.provider_run_id:
        raise HTTPException(
            status_code=400,
            detail="No Dograh run recorded yet for this interview (the candidate may not have joined the call).",
        )

    if not settings.DOGRAH_WORKFLOW_ID:
        raise HTTPException(status_code=400, detail="DOGRAH_WORKFLOW_ID is not configured")

    try:
        run_data = await dograh_client.get_run(settings.DOGRAH_WORKFLOW_ID, interview.provider_run_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch run from Dograh: {e}")

    gathered_context = run_data.get("gathered_context") or {}
    evaluation_data = {
        "source": "dograh",
        "workflow_run_id": run_data.get("id"),
        "call_disposition": gathered_context.get("call_disposition", ""),
        "gathered_context": gathered_context,
        "cost_info": run_data.get("cost_info"),
        "transcript_url": run_data.get("transcript_url"),
        "recording_url": run_data.get("recording_url"),
        "user_recording_url": run_data.get("user_recording_url"),
        "bot_recording_url": run_data.get("bot_recording_url"),
    }

    # Reuses receive_evaluation's merge/idempotency logic rather than
    # duplicating it - applies exactly the fields the webhook would have applied.
    await interview_adapter.receive_evaluation(resume_id, job_id, evaluation_data)

    return {"success": True, "message": "Interview resynced from Dograh"}


# Terminal statuses this endpoint refuses to reopen - COMPLETED/DECLINED/
# NO_SHOW are all closed; a recruiter decision only makes sense for anything
# still active or awaiting review.
_DECLINE_BLOCKED_STATUSES = ("COMPLETED", "DECLINED", "NO_SHOW")


@router.post("/{job_id}/interviews/{resume_id}/decline", response_model=dict)
async def decline_interview(
    job_id: int,
    resume_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manual recruiter action - purely a recorded decision, never inferred
    from transcript/session data. DECLINED is manual-only by design."""
    await _get_job_or_404(job_id, db, current_user.organization_id)

    result = await db.execute(
        select(Interview).where(
            Interview.resume_id == resume_id,
            Interview.job_id == job_id,
        )
    )
    interview = result.scalar_one_or_none()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found for this candidate")

    if interview.status in _DECLINE_BLOCKED_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Interview is already closed (status={interview.status}); cannot mark as declined.",
        )

    interview.status = "DECLINED"
    interview.outcome = "manual_decline"
    await db.commit()

    return {"success": True, "message": "Interview marked as declined"}


# -- update decision -----------------------------------------------------------

@router.patch("/{job_id}/results/{resume_id}/decision", response_model=ScreeningResultResponse)
async def update_screening_decision(
    job_id: int,
    resume_id: int,
    payload: DecisionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_job_or_404(job_id, db, current_user.organization_id)

    # Ownership check
    resume_res = await db.execute(
        select(Resume).where(Resume.id == resume_id, Resume.job_id == job_id)
    )
    resume = resume_res.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found for this job")

    screening_res = await db.execute(
        select(ScreeningResult).where(
            ScreeningResult.resume_id == resume_id,
            ScreeningResult.job_id == job_id
        )
    )
    screening = screening_res.scalar_one_or_none()

    if not screening:
        # If there's no screening result yet but we are setting a decision, we should create one?
        # Typically decisions are only set on evaluated candidates, but maybe we want to force it.
        # For now, let's create a blank one.
        screening = ScreeningResult(
            job_id=job_id,
            resume_id=resume_id,
            score=None
        )
        db.add(screening)

    update_data = payload.model_dump(exclude_unset=True)

    # Phase 4: preload BEFORE mutating screening.decision/.score below - if
    # this ScreeningResult is already linked to an Application (a second HR
    # override on the same result), the preload query will identity-map
    # back to this exact same object, so its old decision/score must be
    # snapshotted before this loop overwrites them, not after.
    audit_context = None
    if "decision" in update_data:
        audit_context = await screening_audit.preload_application_context(
            db, job_id=job_id, resume_ids=[resume_id]
        )

    for key, value in update_data.items():
        setattr(screening, key, value)

    # An HR-set decision is a DecisionAudit event (a pure notes edit is
    # not) - links this ScreeningResult to its Application and keeps
    # Application.status in sync with the override.
    if audit_context is not None:
        screening_audit.record_screening_event(
            db, audit_context, resume_id=resume_id, screening_result=screening,
            actor_type="HR_USER", actor_id=current_user.id,
        )

    await db.commit()
    await db.refresh(screening)

    if update_data.get("decision") == "SHORTLIST":
        await outreach_service.on_decision_shortlisted(job_id, [resume_id])

    # Phase 6: centralized candidate-identity resolution.
    summary = (await get_candidate_summaries(db, [resume_id])).get(resume_id, {})

    return ScreeningResultResponse(
        id=screening.id,
        job_id=job_id,
        resume_id=resume.id,
        score=screening.score,
        semantic_score=screening.semantic_score,
        strengths=screening.strengths,
        gaps=screening.gaps,
        evidence=screening.evidence,
        decision=screening.decision,
        notes=screening.notes,
        created_at=screening.created_at,
        status=resume.status,
        error_message=_safe_error_message(resume),
        display_name=summary.get("display_name"),
        candidate_id=summary.get("candidate_id"),
        applications_count=summary.get("applications_count"),
        evaluation_failed=is_evaluation_failed(screening.notes),
    )


# --- retry a failed AI evaluation ---------------------------------------------
#
# screener.py's per-candidate fallback path (screen_job) leaves a
# ScreeningResult with no score/decision and a "provider error" note when
# every configured LLM provider fails for that one candidate - usually a
# transient outage, not a real evaluation outcome. This lets HR re-run just
# that one candidate's evaluation once the outage has cleared, without
# re-screening (and re-billing) the whole batch.

@router.post("/{job_id}/results/{resume_id}/retry-evaluation", response_model=ScreeningResultResponse)
async def retry_candidate_evaluation(
    job_id: int,
    resume_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = await _get_job_or_404(job_id, db, current_user.organization_id)

    resume_res = await db.execute(
        select(Resume).where(Resume.id == resume_id, Resume.job_id == job_id)
    )
    resume = resume_res.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found for this job")

    try:
        screening = await screener_service.retry_evaluation(db, job=job, resume_id=resume_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Retry failed again - the LLM providers may still be unavailable: {str(e)[:200]}",
        )

    summary = (await get_candidate_summaries(db, [resume_id])).get(resume_id, {})

    return ScreeningResultResponse(
        id=screening.id,
        job_id=job_id,
        resume_id=resume.id,
        score=screening.score,
        semantic_score=screening.semantic_score,
        strengths=screening.strengths,
        gaps=screening.gaps,
        evidence=screening.evidence,
        decision=screening.decision,
        notes=screening.notes,
        created_at=screening.created_at,
        status=resume.status,
        error_message=_safe_error_message(resume),
        display_name=summary.get("display_name"),
        candidate_id=summary.get("candidate_id"),
        applications_count=summary.get("applications_count"),
        raw_candidate_id=resume.candidate_id,
        evaluation_failed=is_evaluation_failed(screening.notes),
    )


@router.patch("/{job_id}/results/bulk-decision", response_model=dict)
async def bulk_update_decision(
    job_id: int,
    payload: BulkDecisionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_job_or_404(job_id, db, current_user.organization_id)
    # Every id must be one of this job's resumes - the whole request is
    # refused otherwise (never a silent partial write, never another
    # organization's resume).
    await tenancy.require_resumes_in_job(db, job_id, payload.resume_ids)

    # Fetch all matching screening results
    res = await db.execute(
        select(ScreeningResult).where(
            ScreeningResult.job_id == job_id,
            ScreeningResult.resume_id.in_(payload.resume_ids)
        )
    )
    screenings = res.scalars().all()

    found_resume_ids = {s.resume_id for s in screenings}

    # What if they don't have a screening result yet? We create blank ones.
    missing_ids = set(payload.resume_ids) - found_resume_ids
    if missing_ids:
        # Verify resumes actually belong to this job
        res_resumes = await db.execute(
            select(Resume.id).where(
                Resume.job_id == job_id,
                Resume.id.in_(missing_ids)
            )
        )
        valid_missing_ids = res_resumes.scalars().all()
        for rid in valid_missing_ids:
            new_sr = ScreeningResult(
                job_id=job_id,
                resume_id=rid,
                score=None,
                decision=payload.decision
            )
            db.add(new_sr)
            screenings.append(new_sr)

    # Phase 4: preload BEFORE mutating .decision below - for a resume whose
    # ScreeningResult is already linked to an Application (a second bulk
    # override on the same results), the preload query identity-maps back
    # to these exact objects, so old decision/score must be snapshotted
    # before the loop below overwrites them, not after. One batched preload
    # for every resume_id in this request, then a pure in-memory
    # DecisionAudit write per result - no N+1 query pattern regardless of
    # how many resume_ids are in the request.
    audit_context = await screening_audit.preload_application_context(
        db, job_id=job_id, resume_ids=[s.resume_id for s in screenings]
    )

    for screening in screenings:
        if hasattr(screening, 'id') and screening.id is not None:
            screening.decision = payload.decision

    for screening in screenings:
        screening_audit.record_screening_event(
            db, audit_context, resume_id=screening.resume_id, screening_result=screening,
            actor_type="HR_USER", actor_id=current_user.id,
        )

    await db.commit()

    if payload.decision == "SHORTLIST":
        await outreach_service.on_decision_shortlisted(job_id, payload.resume_ids)

    return {"message": f"Updated {len(screenings)} candidates", "updated_count": len(screenings)}


# -- batch progress ------------------------------------------------------------

@router.get("/{job_id}/progress", response_model=BatchProgressResponse)
async def get_batch_progress(
    job_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    await _get_job_or_404(job_id, db, current_user.organization_id)

    batches_res = await db.execute(
        select(ScreeningBatch).where(ScreeningBatch.job_id == job_id)
    )
    batches = batches_res.scalars().all()

    batch_details = []
    for batch in batches:
        # A SCREEN batch (see screening_trigger.enqueue_screen_job) never has
        # Resume rows pointing at its batch_id, so total_resumes (assigned
        # directly there) is the only meaningful total. An UPLOAD batch's
        # total_resumes is a snapshot taken at upload time and goes stale if
        # a resume is later deleted from it - live-count it instead so a
        # deleted resume doesn't keep showing up here.
        if batch.batch_type == "SCREEN":
            # Same reasoning as total above: a SCREEN batch has no Resume
            # rows at all under its batch_id, so completed/failed have to
            # come from the batch's own snapshot columns (kept correct by
            # the worker's screen_job handling) rather than a Resume count
            # that would always read 0 - and there's no per-resume
            # "processing" state during screening to count either.
            total = batch.total_resumes
            completed = batch.processed
            failed_count = batch.failed
            processing = 0
        else:
            total_res = await db.execute(
                select(func.count(Resume.id)).where(Resume.batch_id == batch.id)
            )
            total = total_res.scalar_one()

            # Count READY resumes as completed
            completed_res = await db.execute(
                select(func.count(Resume.id)).where(
                    Resume.batch_id == batch.id, Resume.status == "READY"
                )
            )
            completed = completed_res.scalar_one()

            failed_res = await db.execute(
                select(func.count(Resume.id)).where(
                    Resume.batch_id == batch.id, Resume.status == "FAILED"
                )
            )
            failed_count = failed_res.scalar_one()

            processing_res = await db.execute(
                select(func.count(Resume.id)).where(
                    Resume.batch_id == batch.id, Resume.status == "PROCESSING"
                )
            )
            processing = processing_res.scalar_one()

        # Screening decision counts (only for this job - ownership already enforced via batch.job_id)
        shortlisted_res = await db.execute(
            select(func.count(ScreeningResult.id)).where(
                ScreeningResult.job_id == job_id,
                ScreeningResult.decision == "SHORTLIST",
            )
        )
        shortlisted = shortlisted_res.scalar_one()

        review_res = await db.execute(
            select(func.count(ScreeningResult.id)).where(
                ScreeningResult.job_id == job_id,
                ScreeningResult.decision == "REVIEW",
            )
        )
        review = review_res.scalar_one()

        rejected_res = await db.execute(
            select(func.count(ScreeningResult.id)).where(
                ScreeningResult.job_id == job_id,
                ScreeningResult.decision == "REJECT",
            )
        )
        rejected = rejected_res.scalar_one()
        
        pre_screened_out_res = await db.execute(
            select(func.count(ScreeningResult.id)).where(
                ScreeningResult.job_id == job_id,
                ScreeningResult.decision == "PRE_SCREENED_OUT",
            )
        )
        pre_screened_out = pre_screened_out_res.scalar_one()

        batch_details.append(
            BatchProgressDetail(
                batch_id=batch.id,
                status=batch.status,
                total=total,
                processing=processing,
                completed=completed,
                failed=failed_count,
                shortlisted=shortlisted,
                review=review,
                rejected=rejected,
                pre_screened_out=pre_screened_out,
                batch_type=batch.batch_type,
            )
        )

    return BatchProgressResponse(job_id=job_id, batches=batch_details)


