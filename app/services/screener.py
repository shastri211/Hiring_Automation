import json
import logging
from typing import List

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.screening import ScreeningResult
from app.models.profile import CandidateProfile
from app.models.resume import Resume
from app.schemas.screening import ScreeningResultSchema
from app.services.vector_store import vector_store
from app.services.llm_provider import LLMProviderFactory, InvalidEvaluationResultError
from app.models.job import Job
from app.core.config import settings

logger = logging.getLogger(__name__)

def _adaptive_pre_screen(candidates: list, min_keep: int, max_keep: int, gap_threshold: float) -> list:
    """
    Adaptive semantic gating algorithm based on the final approved strategy.
    `candidates` is a list of tuples: (id_or_index, score, ...)
    """
    if not candidates:
        return []
    
    # Sort descending by semantic_score (which is at index 1)
    sorted_cands = sorted(candidates, key=lambda x: x[1], reverse=True)
    
    # 1. Short-circuit for small sets
    if len(sorted_cands) <= min_keep:
        return sorted_cands
        
    scores = [c[1] for c in sorted_cands]
    
    # 2. Gap Analysis
    max_gap = 0.0
    cutoff_idx = len(sorted_cands)
    
    # Look for the largest gap
    for i in range(len(scores) - 1):
        gap = scores[i] - scores[i+1]
        if gap > max_gap:
            max_gap = gap
            # Potential cutoff is after the current score
            best_cutoff_idx = i + 1
            
    if max_gap >= gap_threshold:
        # We found a clear gap
        cutoff_idx = best_cutoff_idx
    else:
        # 3. Fallback to statistical mean for monotonic or tightly clustered
        mean_score = sum(scores) / len(scores)
        # Find how many candidates are above or equal to mean
        above_mean = [c for c in sorted_cands if c[1] >= mean_score]
        cutoff_idx = len(above_mean)
        
    # 4. Safety Bounds Enforcement
    # Floor
    if cutoff_idx < min_keep:
        cutoff_idx = min_keep
    
    # Ceiling
    if cutoff_idx > max_keep:
        cutoff_idx = max_keep
        
    # Ensure we don't go out of bounds of the actual list length
    cutoff_idx = min(cutoff_idx, len(sorted_cands))
    
    return sorted_cands[:cutoff_idx]


class ScreenerService:
    async def screen_job(
        self,
        db: AsyncSession,
        job: Job,
        limit: int = 50,
    ) -> List[ScreeningResult]:
        """Screen candidates for a given job using semantic retrieval and LLM evaluation."""

        # Snapshot all required ORM values before any awaited operation.
        # This prevents SQLAlchemy from attempting implicit async lazy/expired
        # loads later in the workflow.
        job_id = job.id
        job_profile = job.job_profile

        if not job_profile:
            raise ValueError("Job has no structured profile")

        from app.services.embeddings import embedding_router
        from sqlalchemy import func

        # Dynamically set limit to ensure all READY resumes are evaluated
        if limit == 50:
            total_candidates_result = await db.execute(
                select(func.count(Resume.id)).where(Resume.job_id == job_id, Resume.status == "READY")
            )
            total_candidates = total_candidates_result.scalar_one()
            limit = max(total_candidates, 50)

        try:
            embedding, profile_config = await embedding_router.generate_embedding(
                str(job_profile), required_profile_name=job.embedding_profile
            )
        except Exception as e:
            logger.error(f"Failed to generate embedding for job {job_id}: {e}")
            raise ValueError("Job has no valid embedding for semantic search")

        logger.info(
            "Retrieving top %s candidates for job %s from Qdrant",
            limit,
            job_id,
        )

        candidates = await vector_store.search(
            collection_name=profile_config.collection,
            query_vector=embedding,
            limit=limit,
            query_filter={"job_id": job_id},
        )
        
        # --- Pre-Screening Layer (The Gate) ---
        # Sort candidates so the gate works properly.
        # candidates is a list of (candidate_id, semantic_score, payload)
        # Thresholds are sourced via SettingsService (DB-configurable, each
        # field falling back individually to the env default when NULL) -
        # the gate algorithm itself (_adaptive_pre_screen) is unchanged.
        from app.services.settings import settings_service
        min_keep, max_keep, gap_threshold = await settings_service.get_effective_screening_config(db)
        passed_gate = _adaptive_pre_screen(
            candidates,
            min_keep=min_keep,
            max_keep=max_keep,
            gap_threshold=gap_threshold,
        )
        
        # Create a set of IDs that passed
        passed_ids = {c[0] for c in passed_gate}

        results: List[ScreeningResult] = []

        for _candidate_id_str, semantic_score, payload in candidates:
            resume_id = payload.get("resume_id")

            if not resume_id:
                continue

            # Idempotency guard.
            existing = await db.execute(
                select(ScreeningResult).where(
                    ScreeningResult.job_id == job_id,
                    ScreeningResult.resume_id == resume_id,
                )
            )

            if existing.scalar_one_or_none() is not None:
                logger.info(
                    "ScreeningResult for job=%s resume=%s already exists; skipping.",
                    job_id,
                    resume_id,
                )
                continue

            candidate_profile = payload.get("profile", {})
            
            # --- Gate Enforcement ---
            if _candidate_id_str not in passed_ids:
                # PRE_SCREENED_OUT
                screening_result = ScreeningResult(
                    job_id=job_id,
                    resume_id=resume_id,
                    score=None,  # Null LLM score
                    semantic_score=semantic_score,
                    strengths=None,
                    gaps=None,
                    evidence=None,
                    decision="PRE_SCREENED_OUT",
                )
                db.add(screening_result)
                try:
                    await db.flush()
                except IntegrityError:
                    await db.rollback()
                else:
                    results.append(screening_result)
                continue

            # --- Context Optimization (Job-Aware) ---
            candidate_profile = self._sanitize_context(candidate_profile, job_profile)

            # --- Lazy LLM Enrichment (Phase 13.5) ---
            # If this candidate was locally extracted (cheap path), enrich their
            # profile with LLM now — only for candidates that passed the gate.
            # PRE_SCREENED_OUT candidates never reach this block.
            profile_result = await db.execute(
                select(CandidateProfile).where(CandidateProfile.resume_id == resume_id)
            )
            db_profile = profile_result.scalar_one_or_none()
            
            if db_profile and db_profile.extraction_method == "LOCAL":
                logger.info(
                    "Lazy LLM enrichment for resume_id=%s (was LOCAL extracted).",
                    resume_id,
                )
                from app.services.profiler import profiler_service
                resume_result = await db.execute(
                    select(Resume).where(Resume.id == resume_id)
                )
                resume_obj = resume_result.scalar_one_or_none()
                if resume_obj and resume_obj.extracted_text:
                    try:
                        enriched = await profiler_service.profile_candidate(resume_obj.extracted_text)
                        if enriched and isinstance(enriched, dict) and (enriched.get("name") or enriched.get("skills") or enriched.get("experience")):
                            # Persist enriched profile
                            db_profile.name = enriched.get("name", db_profile.name)
                            db_profile.email = (enriched.get("contact") or {}).get("email", db_profile.email)
                            db_profile.phone = (enriched.get("contact") or {}).get("phone", db_profile.phone)
                            db_profile.summary = enriched.get("summary", db_profile.summary)
                            db_profile.total_experience_years = enriched.get("total_experience_years", db_profile.total_experience_years)
                            db_profile.education = enriched.get("education", db_profile.education)
                            db_profile.experience = enriched.get("experience", db_profile.experience)
                            db_profile.skills = enriched.get("skills", db_profile.skills)
                            db_profile.projects = enriched.get("projects", db_profile.projects)
                            db_profile.certifications = enriched.get("certifications", db_profile.certifications)
                            db_profile.languages = enriched.get("languages", db_profile.languages)
                            db_profile.achievements = enriched.get("achievements", db_profile.achievements)
                            db_profile.extraction_method = "LLM_ENRICHED"
                            # Use enriched profile for evaluation
                            candidate_profile = enriched
                            logger.info("Resume %s successfully enriched by LLM.", resume_id)
                    except Exception as enrich_err:
                        logger.warning(
                            "Lazy LLM enrichment failed for resume_id=%s: %s. Using local profile.",
                            resume_id,
                            enrich_err,
                        )

            try:
                eval_result_dict = await self.evaluate_candidate(
                    job_profile,
                    candidate_profile,
                )

                screening_result = ScreeningResult(
                    job_id=job_id,
                    resume_id=resume_id,
                    score=eval_result_dict.get("score", 0.0),
                    semantic_score=semantic_score,
                    strengths=eval_result_dict.get("strengths", []),
                    gaps=eval_result_dict.get("gaps", []),
                    evidence=eval_result_dict.get("evidence", []),
                    decision=eval_result_dict.get("decision", "REVIEW"),
                )

                db.add(screening_result)

                try:
                    await db.flush()
                except IntegrityError:
                    await db.rollback()
                    logger.warning(
                        "Duplicate insert race for job=%s resume=%s; skipping.",
                        job_id,
                        resume_id,
                    )
                    continue

                results.append(screening_result)

            except Exception as e:
                logger.exception(
                    "Failed to evaluate resume_id %s for job %s",
                    resume_id,
                    job_id,
                )
                
                # Persist a fallback screening result to avoid dropping candidates
                screening_result = ScreeningResult(
                    job_id=job_id,
                    resume_id=resume_id,
                    score=None,
                    semantic_score=semantic_score,
                    decision="REVIEW",
                    notes=f"Evaluation failed due to provider error: {str(e)[:200]}"
                )
                db.add(screening_result)
                try:
                    await db.flush()
                except IntegrityError:
                    await db.rollback()
                    continue
                    
                results.append(screening_result)

        await db.commit()
        return results

    async def evaluate_candidate(
        self,
        job_profile: dict,
        candidate_profile: dict,
    ) -> dict:
        prompt = f"""
You are an expert technical recruiter evaluating a candidate for a role.
Do not use keyword-matching. Assess the semantic fit of the candidate against the job requirements.
Never hallucinate missing candidate data. All evidence must be grounded in the candidate profile.

JOB PROFILE:
{json.dumps(job_profile, indent=2)}

CANDIDATE PROFILE:
{json.dumps(candidate_profile, indent=2)}

Return the result strictly matching the provided JSON schema.
The decision must be exactly one of: SHORTLIST, REVIEW, or REJECT.

Expected JSON Schema:
{json.dumps(ScreeningResultSchema.model_json_schema(), indent=2)}
"""

        schema = ScreeningResultSchema.model_json_schema()

        result = await LLMProviderFactory.generate_with_fallback(
            prompt,
            schema,
        )

        # Distinguish evaluation-output failure from provider exhaustion.
        # LLMExhaustionError is already raised by generate_with_fallback when
        # all providers are exhausted — it propagates here unchanged.
        # If a provider responded but the payload is unusable, raise
        # InvalidEvaluationResultError so the per-candidate handler in
        # screen_job can log-and-skip without aborting the rest of the batch.
        if not isinstance(result, dict) or "score" not in result:
            raise InvalidEvaluationResultError(
                f"LLM evaluation returned an unusable payload (missing 'score' key): {result!r}"
            )

        return result
        
    def _sanitize_context(self, candidate_profile: dict, job_profile: dict) -> dict:
        """
        Strips PII and conditionally removes irrelevant fields based on job profile.
        """
        sanitized = dict(candidate_profile)
        
        # Always remove PII/irrelevant fields
        for field in ["name", "email", "phone", "contact", "hobbies"]:
            sanitized.pop(field, None)
            
        # Job-aware conditional fields
        job_reqs = str(job_profile.get("required_capabilities", [])) + str(job_profile.get("preferred_capabilities", [])) + str(job_profile.get("requirements", []))
        job_reqs = job_reqs.lower()
        
        # Languages
        if "languages" in sanitized and not ("language" in job_reqs or "bilingual" in job_reqs):
            # No explicit mention of languages in JD requirements
            sanitized.pop("languages", None)
            
        # Certifications — keep when job explicitly requires credentials or named technologies
        _cert_keywords = ["certif", "licen", "degree", "cpa", "aws", "gcp", "azure"]
        if "certifications" in sanitized and not any(kw in job_reqs for kw in _cert_keywords):
            sanitized.pop("certifications", None)

        return sanitized


screener_service = ScreenerService()