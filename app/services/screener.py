import json
import logging
from typing import List

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.screening import ScreeningResult
from app.models.profile import CandidateProfile
from app.models.resume import Resume
from app.models.interview import Interview
from app.schemas.screening import ScreeningResultSchema, EVALUATION_FAILED_NOTE_PREFIX
from app.services.vector_store import vector_store
from app.services.llm_provider import LLMProviderFactory, InvalidEvaluationResultError
from app.services import screening_audit
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
    # Safe fallback if gap_threshold is misconfigured as <= 0: with every
    # pairwise gap tied at 0.0, the loop below never assigns best_cutoff_idx,
    # yet `max_gap >= gap_threshold` still holds - keep everyone rather than
    # crash with an UnboundLocalError.
    best_cutoff_idx = len(sorted_cands)

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
        organization_id = job.organization_id

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
        min_keep, max_keep, gap_threshold = await settings_service.get_effective_screening_config(db, organization_id)
        passed_gate = _adaptive_pre_screen(
            candidates,
            min_keep=min_keep,
            max_keep=max_keep,
            gap_threshold=gap_threshold,
        )
        
        # Create a set of IDs that passed
        passed_ids = {c[0] for c in passed_gate}

        results: List[ScreeningResult] = []
        # Only app/api/jobs.py's manual HR decision endpoints call
        # outreach_service.on_decision_shortlisted today - the automatic AI
        # screening path here never did, so a candidate the AI itself
        # shortlisted never got an auto-generated interview link or
        # auto-sent email no matter how auto_generate_interview_on_shortlist/
        # auto_email_on_shortlist were configured. Tracked here and fired
        # once, after the batch commits below, so it never runs against
        # ScreeningResults that could still be rolled back.
        shortlisted_resume_ids: List[int] = []

        # Phase 4: one batched preload covering every candidate in this run,
        # so linking each new ScreeningResult to its Application and writing
        # a DecisionAudit entry (below) is pure in-memory lookups inside the
        # loop - not a query per candidate.
        all_resume_ids = [payload.get("resume_id") for _cid, _score, payload in candidates if payload.get("resume_id")]
        audit_context = await screening_audit.preload_application_context(
            db, job_id=job_id, resume_ids=all_resume_ids
        )
        # A crash between an earlier run's ScreeningResult commit and its
        # outreach_service.on_decision_shortlisted call (below) would
        # otherwise permanently skip that resume's interview-link/email
        # automation - the idempotency guard's "already exists, skip" never
        # gives it another chance. Resumes that already have an Interview
        # are excluded from that recovery so a routine re-screen (e.g. new
        # candidates uploaded later) doesn't regenerate and invalidate an
        # already-sent, already-working interview link for everyone already
        # fully processed.
        already_interviewed_resume_ids = set(
            (await db.execute(select(Interview.resume_id).where(Interview.job_id == job_id))).scalars().all()
        )

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

            existing_result = existing.scalar_one_or_none()
            if existing_result is not None:
                if existing_result.decision == "SHORTLIST" and resume_id not in already_interviewed_resume_ids:
                    shortlisted_resume_ids.append(resume_id)
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
                # Each write below runs in its own SAVEPOINT (begin_nested):
                # screen_job commits once at the very end, so an IntegrityError
                # (or any DB error) on one candidate must only unwind that
                # candidate's own insert, never every result already flushed
                # earlier in this same call.
                try:
                    async with db.begin_nested():
                        db.add(screening_result)
                        await db.flush()
                except IntegrityError:
                    pass
                else:
                    screening_audit.record_screening_event(
                        db, audit_context, resume_id=resume_id, screening_result=screening_result, actor_type="SYSTEM",
                    )
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

                try:
                    async with db.begin_nested():
                        db.add(screening_result)
                        await db.flush()
                except IntegrityError:
                    logger.warning(
                        "Duplicate insert race for job=%s resume=%s; skipping.",
                        job_id,
                        resume_id,
                    )
                    continue

                screening_audit.record_screening_event(
                    db, audit_context, resume_id=resume_id, screening_result=screening_result, actor_type="SYSTEM",
                )
                results.append(screening_result)
                if screening_result.decision == "SHORTLIST":
                    shortlisted_resume_ids.append(resume_id)

            except Exception as e:
                logger.exception(
                    "Failed to evaluate resume_id %s for job %s",
                    resume_id,
                    job_id,
                )

                # Persist a fallback screening result to avoid dropping candidates.
                # Runs in its own SAVEPOINT (see comment above) so a DB-level
                # error above (not just an LLM/provider error) can't take down
                # every other candidate already flushed earlier in this call.
                screening_result = ScreeningResult(
                    job_id=job_id,
                    resume_id=resume_id,
                    score=None,
                    semantic_score=semantic_score,
                    decision="REVIEW",
                    notes=f"{EVALUATION_FAILED_NOTE_PREFIX} {str(e)[:200]}"
                )
                try:
                    async with db.begin_nested():
                        db.add(screening_result)
                        await db.flush()
                except IntegrityError:
                    continue

                screening_audit.record_screening_event(
                    db, audit_context, resume_id=resume_id, screening_result=screening_result, actor_type="SYSTEM",
                )
                results.append(screening_result)

        await db.commit()

        if shortlisted_resume_ids:
            from app.services.outreach import outreach_service

            await outreach_service.on_decision_shortlisted(job_id, shortlisted_resume_ids)

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

        # A non-numeric or out-of-range score would otherwise reach the DB
        # column as-is and only surface as an opaque DataError at flush time
        # (see screen_job's per-candidate SAVEPOINT handling) - reject it here
        # with a clear, expected error instead.
        score = result["score"]
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not (0 <= score <= 100):
            raise InvalidEvaluationResultError(
                f"LLM evaluation returned an out-of-range/non-numeric score: {score!r}"
            )

        # strengths/gaps/evidence are written as-is to ScreeningResult's JSON
        # columns and read back through ScreeningResultResponse's
        # `Optional[List[str]]` typing - an LLM returning e.g. a list of
        # objects instead of strings (schema is only a prompt hint, never
        # enforced by the provider) would otherwise persist fine and only
        # blow up as a 500 on every later GET of this row. Coerced here,
        # the one place both screen_job and retry_evaluation funnel through,
        # rather than validated again at each read site.
        for key in ("strengths", "gaps", "evidence"):
            value = result.get(key)
            if not isinstance(value, list):
                result[key] = []
            else:
                result[key] = [item if isinstance(item, str) else json.dumps(item) for item in value]

        return result

    async def retry_evaluation(self, db: AsyncSession, *, job: Job, resume_id: int) -> ScreeningResult:
        """Re-runs the LLM evaluation for one candidate whose ScreeningResult
        is stuck in the fallback/provider-error state (see the `except
        Exception` branch in screen_job above) - e.g. after a transient LLM
        outage that has since cleared. Refuses to touch anything that isn't
        actually in that state, so this can never be used to second-guess or
        silently overwrite a real AI decision.

        On a repeat failure, updates the same placeholder's notes with the
        new error (still no score/decision change) and re-raises, so the
        caller can tell the retry itself failed rather than succeeding with
        a stale response.
        """
        sr_result = await db.execute(
            select(ScreeningResult).where(
                ScreeningResult.job_id == job.id, ScreeningResult.resume_id == resume_id
            )
        )
        screening_result = sr_result.scalar_one_or_none()
        if screening_result is None:
            raise ValueError("No screening result exists yet for this candidate.")
        if not (screening_result.notes and screening_result.notes.startswith(EVALUATION_FAILED_NOTE_PREFIX)):
            raise ValueError("This candidate's evaluation did not fail - there is nothing to retry.")

        profile_result = await db.execute(
            select(CandidateProfile).where(CandidateProfile.resume_id == resume_id)
        )
        profile = profile_result.scalar_one_or_none()
        if profile is None:
            raise ValueError("No candidate profile found for this resume.")

        candidate_profile = {
            "name": profile.name,
            "summary": profile.summary,
            "total_experience_years": profile.total_experience_years,
            "education": profile.education,
            "experience": profile.experience,
            "skills": profile.skills,
            "projects": profile.projects,
            "certifications": profile.certifications,
            "languages": profile.languages,
            "achievements": profile.achievements,
        }
        candidate_profile = self._sanitize_context(candidate_profile, job.job_profile)

        audit_context = await screening_audit.preload_application_context(
            db, job_id=job.id, resume_ids=[resume_id]
        )

        try:
            eval_result = await self.evaluate_candidate(job.job_profile, candidate_profile)
        except Exception as e:
            logger.exception(
                "Retry evaluation failed again for resume_id=%s job=%s", resume_id, job.id
            )
            screening_result.notes = f"{EVALUATION_FAILED_NOTE_PREFIX} {str(e)[:200]}"
            await db.commit()
            raise

        screening_result.score = eval_result.get("score", 0.0)
        screening_result.strengths = eval_result.get("strengths", [])
        screening_result.gaps = eval_result.get("gaps", [])
        screening_result.evidence = eval_result.get("evidence", [])
        screening_result.decision = eval_result.get("decision", "REVIEW")
        screening_result.notes = None

        screening_audit.record_screening_event(
            db, audit_context, resume_id=resume_id, screening_result=screening_result, actor_type="SYSTEM",
        )

        await db.commit()
        await db.refresh(screening_result)
        return screening_result

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