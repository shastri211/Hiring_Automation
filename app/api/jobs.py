import os
import logging
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
from app.schemas.job import JobCreate, JobResponse
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
)
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
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/", response_model=List[JobResponse])
async def list_jobs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).order_by(Job.id.desc()))
    return result.scalars().all()


# -- cross-job processing overview (sidebar > Processing) ----------------------
# Registered before the "/{job_id}" routes below so "/batches/overview" isn't
# swallowed by the int path-converter on job_id.

@router.get("/batches/overview", response_model=List[JobBatchOverviewItem])
async def get_batches_overview(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ScreeningBatch, Job.title, Job.status)
        .join(Job, Job.id == ScreeningBatch.job_id)
        .order_by(ScreeningBatch.created_at.desc())
        .limit(100)
    )
    rows = result.all()
    return [
        JobBatchOverviewItem(
            job_id=batch.job_id,
            job_title=job_title,
            job_status=job_status,
            batch_id=batch.id,
            batch_status=batch.status,
            total=batch.total_resumes,
            processed=batch.processed,
            failed=batch.failed,
            created_at=batch.created_at,
        )
        for batch, job_title, job_status in rows
    ]



# -- helpers -------------------------------------------------------------------

async def _get_job_or_404(job_id: int, db: AsyncSession) -> Job:
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


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
async def create_job(job_in: JobCreate, db: AsyncSession = Depends(get_db)):
    _require_meaningful_description(job_in.description)
    job = Job(title=job_in.title, description=job_in.description)
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
    db: AsyncSession = Depends(get_db)
):
    if not description and not file:
        raise HTTPException(status_code=400, detail="Must provide either a description or a file")
        
    extracted_text = ""
    
    if file:
        os.makedirs("uploads/jobs", exist_ok=True)
        file_path = os.path.join("uploads/jobs", sanitize_filename(file.filename))
        async with aiofiles.open(file_path, 'wb') as out_file:
            content = await file.read()
            await out_file.write(content)
            
        try:
            extractor = get_extractor(file_path, file.content_type)
            extracted_text = await extractor.extract(file_path)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse JD file: {str(e)}")
            
    # Converge paths
    final_description = ""
    if description:
        final_description += description + "\n\n"
    if extracted_text:
        final_description += extracted_text

    _require_meaningful_description(final_description)

    # Re-use existing Job Create logic pipeline
    job = Job(title=title, description=final_description)
    db.add(job)
    await db.flush()

    await _bootstrap_job_profile_and_embedding(job)

    await db.commit()
    await db.refresh(job)
    return job

# -- get job -------------------------------------------------------------------

@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: int, db: AsyncSession = Depends(get_db)):
    return await _get_job_or_404(job_id, db)


@router.post("/{job_id}/pause", response_model=JobResponse)
async def pause_job(job_id: int, db: AsyncSession = Depends(get_db)):
    job = await _get_job_or_404(job_id, db)
    if job.status == "ACTIVE":
        job.status = "PAUSED"
        await db.commit()
        await db.refresh(job)
    return job


@router.post("/{job_id}/resume", response_model=JobResponse)
async def resume_job(job_id: int, db: AsyncSession = Depends(get_db)):
    job = await _get_job_or_404(job_id, db)
    if job.status == "PAUSED":
        job.status = "ACTIVE"
        await db.commit()
        await db.refresh(job)
        # Note: In-flight batches that were paused might need to be re-enqueued,
        # but current architecture just skips new items when paused. So resume 
        # means subsequent items in queue will process, or new batches can be triggered.
    return job


@router.post("/{job_id}/archive", response_model=JobResponse)
async def archive_job(job_id: int, db: AsyncSession = Depends(get_db)):
    job = await _get_job_or_404(job_id, db)
    if job.status != "ARCHIVED":
        job.status = "ARCHIVED"
        await db.commit()
        await db.refresh(job)
    return job


@router.delete("/{job_id}", status_code=204)
async def delete_job(job_id: int, db: AsyncSession = Depends(get_db)):
    job = await _get_job_or_404(job_id, db)
    
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

    # Delete from DB (manual cascade to avoid FK constraint errors)
    from sqlalchemy import delete
    await db.execute(delete(ScreeningResult).where(ScreeningResult.job_id == job_id))
    await db.execute(delete(CandidateProfile).where(CandidateProfile.resume_id.in_(
        select(Resume.id).where(Resume.job_id == job_id)
    )))
    await db.execute(delete(Interview).where(Interview.job_id == job_id))
    await db.execute(delete(Resume).where(Resume.job_id == job_id))
    await db.execute(delete(ScreeningBatch).where(ScreeningBatch.job_id == job_id))

    await db.delete(job)
    await db.commit()
    
    return None


# -- trigger screening ---------------------------------------------------------

@router.post("/{job_id}/screen", status_code=202)
async def trigger_screening(job_id: int, db: AsyncSession = Depends(get_db)):
    job = await _get_job_or_404(job_id, db)

    # total_resumes = candidates this run will actually attempt to screen, so
    # the cross-job Processing overview (/jobs/batches/overview) shows real
    # progress instead of a permanent 0/0/0 row for screening-trigger batches.
    ready_count_res = await db.execute(
        select(func.count(Resume.id)).where(Resume.job_id == job_id, Resume.status == "READY")
    )
    ready_count = ready_count_res.scalar_one()

    batch = ScreeningBatch(job_id=job.id, status="PROCESSING", total_resumes=ready_count)
    db.add(batch)
    await db.commit()
    await db.refresh(batch)

    await queue_service.enqueue_task({
        "action": "screen_job",
        "job_id": job.id,
        "batch_id": batch.id,
    })

    return {"message": "Screening batch created and enqueued", "batch_id": batch.id}


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
):
    await _get_job_or_404(job_id, db)

    query = (
        select(
            Resume,
            ScreeningResult,
            CandidateProfile.name.label("candidate_name")
        )
        .outerjoin(ScreeningResult, (ScreeningResult.resume_id == Resume.id) & (ScreeningResult.job_id == job_id))
        .outerjoin(CandidateProfile, CandidateProfile.resume_id == Resume.id)
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

    items = []
    for row in rows:
        resume = row.Resume
        sr = row.ScreeningResult
        cname = row.candidate_name
        
        # Centralized candidate identity
        display_name = cname if cname else (resume.filename.rsplit('.', 1)[0] if resume.filename else f"Resume #{resume.id}")
        
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
                display_name=display_name
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
                display_name=display_name
            ))

    return PaginatedScreeningResultResponse(
        items=items, total=total, page=page, page_size=page_size
    )


# -- candidate detail ----------------------------------------------------------

@router.get("/{job_id}/results/{resume_id}", response_model=CandidateDetailResponse)
async def get_candidate_detail(
    job_id: int, resume_id: int, db: AsyncSession = Depends(get_db)
):
    await _get_job_or_404(job_id, db)

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

    # We need display_name for the single view too
    display_name = profile.name if profile and profile.name else (resume.filename.rsplit('.', 1)[0] if resume.filename else f"Resume #{resume.id}")
    
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
            display_name=display_name
        )

    return CandidateDetailResponse(
        resume_id=resume.id,
        filename=resume.filename,
        status=resume.status,
        error_message=_safe_error_message(resume),
        profile=profile_detail,
        screening=screening_response,
        interview=InterviewResponse.model_validate(interview) if interview else None,
    )


# -- manual Dograh resync (bounded safety net; webhooks aren't guaranteed --
# -- exactly-once-ever delivery) -----------------------------------------------

@router.post("/{job_id}/interviews/{resume_id}/resync", response_model=dict)
async def resync_interview(
    job_id: int,
    resume_id: int,
    db: AsyncSession = Depends(get_db),
):
    await _get_job_or_404(job_id, db)

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


# -- update decision -----------------------------------------------------------

@router.patch("/{job_id}/results/{resume_id}/decision", response_model=ScreeningResultResponse)
async def update_screening_decision(
    job_id: int,
    resume_id: int,
    payload: DecisionUpdate,
    db: AsyncSession = Depends(get_db)
):
    await _get_job_or_404(job_id, db)
    
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
    for key, value in update_data.items():
        setattr(screening, key, value)
        
    await db.commit()
    await db.refresh(screening)

    if update_data.get("decision") == "SHORTLIST":
        await outreach_service.on_decision_shortlisted(job_id, [resume_id])

    profile_res = await db.execute(
        select(CandidateProfile).where(CandidateProfile.resume_id == resume_id)
    )
    profile = profile_res.scalar_one_or_none()
    display_name = profile.name if profile and profile.name else (resume.filename.rsplit('.', 1)[0] if resume.filename else f"Resume #{resume.id}")
    
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
        display_name=display_name
    )


@router.patch("/{job_id}/results/bulk-decision", response_model=dict)
async def bulk_update_decision(
    job_id: int,
    payload: BulkDecisionUpdate,
    db: AsyncSession = Depends(get_db)
):
    await _get_job_or_404(job_id, db)
    
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
            
    for screening in screenings:
        if hasattr(screening, 'id') and screening.id is not None:
            screening.decision = payload.decision
            
    await db.commit()

    if payload.decision == "SHORTLIST":
        await outreach_service.on_decision_shortlisted(job_id, payload.resume_ids)

    return {"message": f"Updated {len(screenings)} candidates", "updated_count": len(screenings)}


# -- batch progress ------------------------------------------------------------

@router.get("/{job_id}/progress", response_model=BatchProgressResponse)
async def get_batch_progress(job_id: int, db: AsyncSession = Depends(get_db)):
    await _get_job_or_404(job_id, db)

    batches_res = await db.execute(
        select(ScreeningBatch).where(ScreeningBatch.job_id == job_id)
    )
    batches = batches_res.scalars().all()

    batch_details = []
    for batch in batches:
        total = batch.total_resumes

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
            )
        )

    return BatchProgressResponse(job_id=job_id, batches=batch_details)


