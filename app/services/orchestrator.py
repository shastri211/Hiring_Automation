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
                # Stage 1: ResumeProcessing
                if resume.workflow_stage == "UPLOADED":
                    logger.info(f"Orchestrator: Extracing text for resume {resume_id}")
                    file_path = os.path.join(storage_service.base_dir, resume.storage_key)
                    extractor = get_extractor(file_path)
                    resume.extracted_text = await extractor.extract(file_path)
                    resume.workflow_stage = "EXTRACTED"
                    await session.commit()

                # Stage 2: CandidateProfiling (Hybrid Local/LLM)
                if resume.workflow_stage == "EXTRACTED":
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

                    profile_result = await session.execute(
                        select(CandidateProfile).where(CandidateProfile.resume_id == resume_id)
                    )
                    existing_profile = profile_result.scalar_one_or_none()
                    if not existing_profile:
                        profile = CandidateProfile(
                            resume_id=resume.id,
                            name=profile_data.get("name"),
                            email=(profile_data.get("contact") or {}).get("email"),
                            phone=(profile_data.get("contact") or {}).get("phone"),
                            summary=profile_data.get("summary"),
                            total_experience_years=profile_data.get("total_experience_years"),
                            education=profile_data.get("education", []),
                            experience=profile_data.get("experience", []),
                            skills=profile_data.get("skills", []),
                            projects=profile_data.get("projects", []),
                            certifications=profile_data.get("certifications", []),
                            languages=profile_data.get("languages", []),
                            achievements=profile_data.get("achievements", []),
                            extraction_method=extraction_method,
                            canonical_text=canonical_text,
                        )
                        session.add(profile)
                    else:
                        existing_profile.name = profile_data.get("name")
                        existing_profile.email = (profile_data.get("contact") or {}).get("email")
                        existing_profile.phone = (profile_data.get("contact") or {}).get("phone")
                        existing_profile.summary = profile_data.get("summary")
                        existing_profile.total_experience_years = profile_data.get("total_experience_years")
                        existing_profile.education = profile_data.get("education", [])
                        existing_profile.experience = profile_data.get("experience", [])
                        existing_profile.skills = profile_data.get("skills", [])
                        existing_profile.projects = profile_data.get("projects", [])
                        existing_profile.certifications = profile_data.get("certifications", [])
                        existing_profile.languages = profile_data.get("languages", [])
                        existing_profile.achievements = profile_data.get("achievements", [])
                        existing_profile.extraction_method = extraction_method
                        existing_profile.canonical_text = canonical_text

                    resume.workflow_stage = "PROFILED"
                    await session.commit()

                # Stage 3: SemanticMatching
                if resume.workflow_stage == "PROFILED":
                    logger.info(f"Orchestrator: Embedding candidate {resume_id}")
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
                    
                # Idempotent batch accounting
                if resume.batch_id:
                    from app.models.batch import ScreeningBatch
                    from sqlalchemy import func

                    batch_res = await session.execute(
                        select(ScreeningBatch).where(ScreeningBatch.id == resume.batch_id)
                    )
                    batch = batch_res.scalar_one_or_none()

                    if batch:
                        # Count the terminal states from the resumes themselves.
                        # This keeps retries/idempotency from double-incrementing counters.
                        processed_res = await session.execute(
                            select(func.count(Resume.id)).where(
                                Resume.batch_id == resume.batch_id,
                                Resume.status == "READY",
                            )
                        )
                        failed_res = await session.execute(
                            select(func.count(Resume.id)).where(
                                Resume.batch_id == resume.batch_id,
                                Resume.status == "FAILED",
                            )
                        )

                        batch.processed = processed_res.scalar_one()
                        batch.failed = failed_res.scalar_one()

                        if batch.processed + batch.failed >= batch.total_resumes:
                            batch.status = "COMPLETED"

                        await session.commit()
                    
                    logger.info(f"Orchestrator: Candidate {resume_id} fully processed for ingestion.")

            except Exception as e:
                logger.exception(f"Error processing resume {resume_id} at stage {resume.workflow_stage}: {e}")
                resume.error_message = str(e)
                resume.status = "FAILED"
                await session.commit()
                raise e

orchestrator = RecruitmentOrchestrator()
