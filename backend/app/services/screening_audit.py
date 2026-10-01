"""ScreeningResult <-> Application linkage and DecisionAudit trail (Phase 4).

Every ScreeningResult - whether produced by automated screening
(app/services/screener.py) or an HR override (app/api/jobs.py's decision
endpoints) - is linked to the Application it belongs to, and every such
write is recorded as a DecisionAudit entry so the full history of a
candidate's standing on a job (automated and human) is reconstructable.

Callers preload a ScreeningAuditContext once per job/batch of resume_ids
(a handful of batched queries) and then call record_screening_event() per
result purely in-memory - this is what keeps screen_job's per-candidate
loop and the bulk-decision endpoint free of an N+1 query pattern.
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resume import Resume
from app.models.application import Application
from app.models.screening import ScreeningResult
from app.models.decision_audit import DecisionAudit
from app.services import candidate_identity

logger = logging.getLogger(__name__)


@dataclass
class ScreeningAuditContext:
    job_id: int
    candidate_id_by_resume_id: Dict[int, int]
    resolved_candidate_id_by_candidate_id: Dict[int, int]
    application_by_candidate_id: Dict[int, Application]
    current_result_by_application_id: Dict[int, ScreeningResult]
    # Snapshotted (decision, score) at preload time, as plain values rather
    # than a live attribute read off current_result_by_application_id's
    # object. Needed because an in-place HR override reuses the SAME
    # ScreeningResult object as its own "prior" result (identity-mapped by
    # SQLAlchemy) - reading .decision off that object lazily, after the
    # caller has already mutated it to the new value, would silently make
    # old_decision equal new_decision.
    old_decision_score_by_application_id: Dict[int, tuple]
    audited_application_ids: Set[int] = field(default_factory=set)


async def preload_application_context(
    db: AsyncSession, *, job_id: int, resume_ids: List[int]
) -> ScreeningAuditContext:
    """One batched round of queries covering every resume_id, instead of a
    per-resume lookup inside whatever loop calls record_screening_event."""
    candidate_id_by_resume_id: Dict[int, int] = {}
    if resume_ids:
        rows = await db.execute(select(Resume.id, Resume.candidate_id).where(Resume.id.in_(resume_ids)))
        candidate_id_by_resume_id = {rid: cid for rid, cid in rows.all() if cid is not None}

    # Merge-chain resolution isn't itself batchable into a single query, but
    # is done at most once per DISTINCT candidate_id (not per resume) -
    # merges are rare and chains are shallow in practice, so this stays a
    # small, bounded cost rather than the N+1 this phase is meant to avoid.
    distinct_candidate_ids = set(candidate_id_by_resume_id.values())
    resolved_candidate_id_by_candidate_id: Dict[int, int] = {
        cid: await candidate_identity.resolve_canonical_candidate_id(db, cid) for cid in distinct_candidate_ids
    }

    application_by_candidate_id: Dict[int, Application] = {}
    resolved_ids = set(resolved_candidate_id_by_candidate_id.values())
    if resolved_ids:
        apps = (
            await db.execute(
                select(Application).where(Application.job_id == job_id, Application.candidate_id.in_(resolved_ids))
            )
        ).scalars().all()
        application_by_candidate_id = {a.candidate_id: a for a in apps}

    application_ids = [a.id for a in application_by_candidate_id.values()]

    current_result_by_application_id: Dict[int, ScreeningResult] = {}
    old_decision_score_by_application_id: Dict[int, tuple] = {}
    if application_ids:
        results = (
            await db.execute(select(ScreeningResult).where(ScreeningResult.application_id.in_(application_ids)))
        ).scalars().all()
        current_result_by_application_id = {r.application_id: r for r in results}
        # Snapshot now, before the caller has a chance to mutate any of
        # these ORM objects in place (see the field comment above).
        old_decision_score_by_application_id = {r.application_id: (r.decision, r.score) for r in results}

    audited_application_ids: Set[int] = set()
    if application_ids:
        rows = (
            await db.execute(
                select(DecisionAudit.application_id).where(DecisionAudit.application_id.in_(application_ids)).distinct()
            )
        ).scalars().all()
        audited_application_ids = set(rows)

    return ScreeningAuditContext(
        job_id=job_id,
        candidate_id_by_resume_id=candidate_id_by_resume_id,
        resolved_candidate_id_by_candidate_id=resolved_candidate_id_by_candidate_id,
        application_by_candidate_id=application_by_candidate_id,
        current_result_by_application_id=current_result_by_application_id,
        old_decision_score_by_application_id=old_decision_score_by_application_id,
        audited_application_ids=audited_application_ids,
    )


def record_screening_event(
    db: AsyncSession,
    context: ScreeningAuditContext,
    *,
    resume_id: int,
    screening_result: ScreeningResult,
    actor_type: str,
    actor_id: Optional[int] = None,
) -> None:
    """Links screening_result to its Application and appends a DecisionAudit
    entry, entirely from the preloaded context - no queries here.

    Silently skips linkage (logs a warning) if the resume has no resolved
    candidate or no Application yet exists for (candidate, job) - this can
    only happen for data that predates candidate identity resolution, and
    should never block the screening result itself from being saved.
    """
    candidate_id = context.candidate_id_by_resume_id.get(resume_id)
    if candidate_id is None:
        logger.warning(
            "screening_audit: resume %s has no resolved candidate_id; skipping Application/DecisionAudit linkage.",
            resume_id,
        )
        return

    resolved_id = context.resolved_candidate_id_by_candidate_id.get(candidate_id)
    application = context.application_by_candidate_id.get(resolved_id) if resolved_id is not None else None
    if application is None:
        logger.warning(
            "screening_audit: no Application found for resume %s (candidate %s, job %s); "
            "skipping DecisionAudit linkage.",
            resume_id, candidate_id, context.job_id,
        )
        return

    prior_result = context.current_result_by_application_id.get(application.id)
    old_decision, old_score = context.old_decision_score_by_application_id.get(application.id, (None, None))

    # Exactly one ScreeningResult is ever "current" per Application - the
    # one this event is about takes over the link, the previous one (if
    # different) keeps its data but is no longer the authoritative result.
    if prior_result is not None and prior_result is not screening_result:
        prior_result.application_id = None

    screening_result.application_id = application.id

    event_type = (
        "HR_OVERRIDE" if actor_type == "HR_USER"
        else ("AI_RESCREEN" if application.id in context.audited_application_ids else "AI_SCREEN")
    )
    db.add(DecisionAudit(
        application_id=application.id,
        event_type=event_type,
        actor_type=actor_type,
        actor_id=actor_id,
        old_decision=old_decision,
        new_decision=screening_result.decision,
        old_score=old_score,
        new_score=screening_result.score,
    ))

    context.audited_application_ids.add(application.id)
    context.current_result_by_application_id[application.id] = screening_result
    context.old_decision_score_by_application_id[application.id] = (screening_result.decision, screening_result.score)
    application.status = screening_result.decision
