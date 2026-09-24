import os
import traceback
from sqlalchemy import select, update
from app.db.session import AsyncSessionLocal
from app.models.resume import Resume
from app.models.profile import CandidateProfile
from app.models.job import Job
from app.models.screening import ScreeningResult
from app.services.storage import storage_service
from app.services.extractor.factory import get_extractor
from app.services.profiler import profiler_service
from app.services.embeddings import embedding_router
from app.services.vector_store import vector_store
from app.services.extractor.local_profiler import LocalProfilerService
from app.services import candidate_identity
from app.services import resume_reuse
from app.services import screening_trigger
from app.services.model_registry import model_registry
import json

import logging
logger = logging.getLogger(__name__)

# Fields considered "meaningful" for a CandidateProfile.
# A profile is valid if ANY of these keys maps to a truthy value.
_CANDIDATE_MEANINGFUL_FIELDS = frozenset({
    "name", "contact", "summary", "experience", "education",
    "skills", "projects", "certifications", "languages",
    "achievements", "total_experience_years",
})


def _is_valid_profile(profile_data: dict) -> bool:
    """Return True if profile_data contains at least one meaningful field with a truthy value.

    Rejects only completely empty dicts or dicts where every meaningful field is
    None / empty string / empty list / 0 / False.
    """
    if not isinstance(profile_data, dict) or not profile_data:
        return False
    for field in _CANDIDATE_MEANINGFUL_FIELDS:
        value = profile_data.get(field)
        if value:  # non-None, non-empty string, non-empty list, non-zero number
            return True
    return False

async def update_batch_progress(session, batch_id: int, allow_complete: bool = True) -> None:
    """Recompute a ScreeningBatch's processed/failed counters from the
    current Resume rows in it, and commit.

    Recounting (rather than incrementing) keeps this idempotent/race-safe
    against retries and concurrent workers. Shared by the orchestrator's
    success path, its per-attempt failure path, and the worker's
    permanent-failure path (fail_task_permanently) so a batch where a resume
    fails outright still gets an accurate, prompt processed/failed count
    instead of waiting on some other resume in the batch to eventually
    succeed.

    `allow_complete=False` (used for a resume's per-attempt transient
    failure, which may still succeed on retry) updates the counters for
    visibility but never flips the batch to COMPLETED - only a resume's
    truly terminal outcome (READY, or retries exhausted) may do that.
    """
    from sqlalchemy import func
    from app.models.batch import ScreeningBatch

    batch_res = await session.execute(
        select(ScreeningBatch).where(ScreeningBatch.id == batch_id)
    )
    batch = batch_res.scalar_one_or_none()
    if not batch:
        return

    processed_res = await session.execute(
        select(func.count(Resume.id)).where(
            Resume.batch_id == batch_id, Resume.status == "READY"
        )
    )
    failed_res = await session.execute(
        select(func.count(Resume.id)).where(
            Resume.batch_id == batch_id, Resume.status == "FAILED"
        )
    )

    batch.processed = processed_res.scalar_one()
    batch.failed = failed_res.scalar_one()

    if allow_complete and batch.processed + batch.failed >= batch.total_resumes:
        batch.status = "COMPLETED"

    await session.commit()


class RecruitmentOrchestrator:

    async def process_candidate(self, resume_id: int):
        async with AsyncSessionLocal() as session:
            # 1. Fetch Resume & Job (with row lock to prevent concurrent processing of the same resume)
            try:
                result = await session.execute(
                    select(Resume).where(Resume.id == resume_id).with_for_update(nowait=True)
                )
                resume = result.scalar_one_or_none()
            except Exception as e:
                logger.exception(f"Resume {resume_id} is locked by another worker: {e}")
                raise ValueError("Resume locked")
                
            if not resume:
                logger.warning(f"Resume {resume_id} not found.")
                return

            # Idempotency / completion check
            if resume.status == "READY":
                return

            if resume.status != "PROCESSING":
                resume.status = "PROCESSING"
                resume.error_message = None
                await session.commit()
                
            job_result = await session.execute(select(Job).where(Job.id == resume.job_id))
            job = job_result.scalar_one_or_none()
            if not job or not job.job_profile:
                logger.error(f"Job or Job Profile is missing for resume {resume_id}")
                resume.status = "FAILED"
                resume.error_message = "Permanent Failure: Job or Job Profile is missing."
                await session.commit()
                return

            if job.status != "ACTIVE":
                logger.info(f"Job {job.id} is {job.status}. Skipping resume {resume_id}.")
                # If the job is paused/archived, we just drop the current processing attempt.
                # When job resumes, it might need to re-enqueue or we leave it in UPLOADED/PROCESSING state.
                # Let's revert back to UPLOADED so it can be picked up again later if re-enqueued?
                # Actually, leaving it PROCESSING means it might be stuck. Reverting to UPLOADED is safer.
                resume.status = "UPLOADED"
                await session.commit()
                return

            try:
                # Phase 3: is there another (any job, any candidate) resume
                # with this exact file_hash whose content-derived work we can
                # copy instead of recomputing? Resolved once, up front, and
                # reused across whichever of Stages 1-3 below still apply -
                # byte-identical content extracts/structures identically
                # regardless of which prior run produced it, so this is a
                # pure optimization, never a correctness concern. Screening
                # itself is untouched: it's always computed fresh per
                # (job_id, resume_id) regardless of what was reused upstream.
                reusable_source = await resume_reuse.find_reusable_source(
                    session, file_hash=resume.file_hash, exclude_resume_id=resume.id,
                    organization_id=job.organization_id,
                )

                # Phase 4: did this resume turn out to be a new version of an
                # *existing* Application (same candidate, same job, a
                # different resume than the one currently on file)? Set in
                # Stage 2 below; if so, once this resume reaches READY we
                # trigger a fresh job-scoped screening pass so the new
                # version actually gets scored, not just filed away.
                # Note: if a crash happens between Stage 2's commit and
                # Stage 3 completing, a retry resumes at Stage 3 without
                # re-running Stage 2, so this flag would default back to
                # False here even though a real swap happened earlier in a
                # prior attempt - a narrow, self-limiting window not worth
                # persisting extra state to close.
                resume_is_version_swap = False

                # Stage 1: ResumeProcessing
                if resume.workflow_stage == "UPLOADED":
                    if reusable_source and reusable_source.extracted_text is not None:
                        logger.info(
                            f"Orchestrator: Reusing extracted text from resume {reusable_source.id} "
                            f"for resume {resume_id} (same file_hash)."
                        )
                        resume.extracted_text = reusable_source.extracted_text
                    else:
                        logger.info(f"Orchestrator: Extracing text for resume {resume_id}")
                        file_path = os.path.join(storage_service.base_dir, resume.storage_key)
                        extractor = get_extractor(file_path)
                        resume.extracted_text = await extractor.extract(file_path)
                    resume.workflow_stage = "EXTRACTED"
                    await session.commit()

                # Stage 2: CandidateProfiling (Hybrid Local/LLM)
                if resume.workflow_stage == "EXTRACTED":
                    source_profile = None
                    if reusable_source:
                        source_profile_result = await session.execute(
                            select(CandidateProfile).where(CandidateProfile.resume_id == reusable_source.id)
                        )
                        source_profile = source_profile_result.scalar_one_or_none()

                    if source_profile:
                        logger.info(
                            f"Orchestrator: Reusing candidate profile from resume {reusable_source.id} "
                            f"for resume {resume_id} (same file_hash)."
                        )
                        fields = {
                            "name": source_profile.name,
                            "email": source_profile.email,
                            "phone": source_profile.phone,
                            "summary": source_profile.summary,
                            "total_experience_years": source_profile.total_experience_years,
                            "education": source_profile.education,
                            "experience": source_profile.experience,
                            "skills": source_profile.skills,
                            "projects": source_profile.projects,
                            "certifications": source_profile.certifications,
                            "languages": source_profile.languages,
                            "achievements": source_profile.achievements,
                            "extraction_method": source_profile.extraction_method,
                            "canonical_text": source_profile.canonical_text,
                        }
                    else:
                        logger.info(f"Orchestrator: Profiling candidate {resume_id} (Local First)")

                        local_profile_data, canonical_text, confidence = LocalProfilerService.profile_candidate(resume.extracted_text)

                        if confidence.get("is_insufficient", True):
                            logger.warning(f"Orchestrator: Local extraction insufficient for resume {resume_id}. Falling back to LLM.")
                            profile_data = await profiler_service.profile_candidate(resume.extracted_text)
                            extraction_method = "LLM_ENRICHED"

                            if not _is_valid_profile(profile_data):
                                raise ValueError(
                                    "LLM returned an empty or invalid candidate profile "
                                    "(all meaningful fields are missing or empty)."
                                )
                        else:
                            profile_data = local_profile_data
                            extraction_method = "LOCAL"

                        fields = {
                            "name": profile_data.get("name"),
                            "email": (profile_data.get("contact") or {}).get("email"),
                            "phone": (profile_data.get("contact") or {}).get("phone"),
                            "summary": profile_data.get("summary"),
                            "total_experience_years": profile_data.get("total_experience_years"),
                            "education": profile_data.get("education", []),
                            "experience": profile_data.get("experience", []),
                            "skills": profile_data.get("skills", []),
                            "projects": profile_data.get("projects", []),
                            "certifications": profile_data.get("certifications", []),
                            "languages": profile_data.get("languages", []),
                            "achievements": profile_data.get("achievements", []),
                            "extraction_method": extraction_method,
                            "canonical_text": canonical_text,
                        }

                    profile_result = await session.execute(
                        select(CandidateProfile).where(CandidateProfile.resume_id == resume_id)
                    )
                    existing_profile = profile_result.scalar_one_or_none()
                    if not existing_profile:
                        profile = CandidateProfile(resume_id=resume.id, **fields)
                        session.add(profile)
                    else:
                        for field_name, value in fields.items():
                            setattr(existing_profile, field_name, value)

                    profile_row = existing_profile if existing_profile else profile

                    # Candidate identity resolution + Application bookkeeping
                    # (Phase 2). Whether this was a resume-version swap on an
                    # existing Application is recorded so Stage 3 can trigger
                    # a fresh screening pass once the resume is READY.
                    resolved_candidate_id = await candidate_identity.resolve_candidate_for_resume(
                        session, resume, profile_row, organization_id=job.organization_id
                    )
                    _application, resume_is_version_swap = await candidate_identity.get_or_create_application(
                        session, candidate_id=resolved_candidate_id, job_id=job.id, resume=resume
                    )

                    resume.workflow_stage = "PROFILED"
                    await session.commit()

                # Stage 3: SemanticMatching
                if resume.workflow_stage == "PROFILED":
                    profile_result = await session.execute(
                        select(CandidateProfile).where(CandidateProfile.resume_id == resume_id)
                    )
                    prof = profile_result.scalar_one()
                    # reconstruct dict
                    prof_dict = {
                        "name": prof.name,
                        "contact": {
                            "email": prof.email,
                            "phone": prof.phone,
                        },
                        "summary": prof.summary,
                        "total_experience_years": prof.total_experience_years,
                        "education": prof.education,
                        "experience": prof.experience,
                        "skills": prof.skills,
                        "projects": prof.projects,
                        "certifications": prof.certifications,
                        "languages": prof.languages,
                        "achievements": prof.achievements,
                    }
                                        
                    if prof.canonical_text:
                        text_to_embed = prof.canonical_text
                    else:
                        text_to_embed = json.dumps(prof_dict)

                    # Reuse only applies when this job's embedding profile is
                    # pinned (job.embedding_profile is set at job creation -
                    # see _bootstrap_job_profile_and_embedding) so the target
                    # collection is known up front; a job without one always
                    # falls through to computing fresh, same as today.
                    reused_vector = None
                    target_profile_config = (
                        model_registry.get_profile_by_model(job.embedding_profile) if job.embedding_profile else None
                    )
                    if reusable_source and target_profile_config:
                        reused_vector = await resume_reuse.get_reusable_embedding(
                            source=reusable_source, profile_config=target_profile_config
                        )

                    if reused_vector is not None:
                        logger.info(
                            f"Orchestrator: Reusing embedding from resume {reusable_source.id} for resume "
                            f"{resume_id} (same file_hash, collection {target_profile_config.collection})."
                        )
                        embedding, profile_config = reused_vector, target_profile_config
                    else:
                        logger.info(f"Orchestrator: Embedding candidate {resume_id}")
                        embedding, profile_config = await embedding_router.generate_embedding(
                            text_to_embed, required_profile_name=job.embedding_profile
                        )

                    await vector_store.create_collection(profile_config.collection, profile_config.dimensions, profile_config.metric)
                    await vector_store.add_points(
                        collection_name=profile_config.collection,
                        ids=[resume.id],
                        vectors=[embedding],
                        payloads=[{"resume_id": resume.id, "job_id": job.id, "profile": prof_dict}]
                    )
                    
                    resume.workflow_stage = "EMBEDDED"
                    resume.status = "READY"
                    await session.commit()

                    # Phase 4: this resume replaced the current resume on an
                    # already-existing Application - it needs its own fresh
                    # ScreeningResult, which only happens if screen_job runs
                    # again for this job. Best-effort: a failure to enqueue
                    # must never undo this resume's already-successful
                    # processing, so it's logged rather than raised.
                    if resume_is_version_swap:
                        try:
                            await screening_trigger.enqueue_screen_job(session, job.id)
                            logger.info(
                                f"Orchestrator: resume {resume_id} is a version swap for job {job.id}; "
                                f"triggered a fresh screening pass."
                            )
                        except Exception:
                            logger.exception(
                                f"Orchestrator: failed to auto-trigger re-screening for job {job.id} "
                                f"after resume {resume_id} version swap."
                            )

                # Idempotent batch accounting
                if resume.batch_id:
                    await update_batch_progress(session, resume.batch_id)

                    logger.info(f"Orchestrator: Candidate {resume_id} fully processed for ingestion.")

            except Exception as e:
                logger.exception(f"Error processing resume {resume_id} at stage {resume.workflow_stage}: {e}")
                resume.error_message = str(e)
                resume.status = "FAILED"
                await session.commit()
                if resume.batch_id:
                    # Not necessarily terminal - the worker may still retry
                    # this resume, so don't let the batch flip to COMPLETED
                    # here (fail_task_permanently does that once retries are
                    # truly exhausted).
                    await update_batch_progress(session, resume.batch_id, allow_complete=False)
                raise e

orchestrator = RecruitmentOrchestrator()
