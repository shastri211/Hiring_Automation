"""Phase 1 backfill: populate Candidate and Application from existing data.

This is a required, one-time migration step for the Candidate/Resume/
Application schema foundation (see the three Phase 1 Alembic revisions:
5f26aa062cbb, 588b759e7977, cb07343150ec). Run it once, from the repo root,
with the app's normal environment/venv active, after those migrations have
been applied and before any Phase 2 code (which reads/writes Application
directly) is deployed:

    python -m scripts.backfill_candidates_applications

What it does, in two steps:

1. Candidate resolution - every Resume without a candidate_id gets one.
   Resumes whose CandidateProfile shares the same normalized email are
   resolved to the same Candidate (exact-match only, the same auto-link
   rule used for live matching - this is identity that CAN be reliably
   established). Resumes with no extractable email each get their own
   placeholder Candidate; no fuzzy (name/phone) matching is attempted here,
   per the approved decision to never silently merge and to not block
   migration on manual cleanup.

2. Application backfill, grouped by (candidate_id, job_id) - one job at a
   time. Because Application has a UNIQUE(candidate_id, job_id) constraint,
   multiple pre-existing Resume rows that resolve to the same candidate and
   job cannot each become their own Application:
     - current_resume_id is chosen deterministically: the resume with the
       latest created_at in the group (ties broken by highest id).
     - every resume in the group (including the chosen one) gets an
       ApplicationResumeHistory row, so none are lost.
     - every ScreeningResult in the group is preserved: none are deleted or
       moved. The result belonging to the chosen current_resume gets its
       application_id set (the one "live" link). Every result in the group
       (including that one) also gets a DecisionAudit row, in chronological
       order, so the full historical score/decision progression survives
       even for resumes that lost the "current" slot.

Safe to re-run: resumes that already have a candidate_id are left alone,
(candidate_id, job_id) pairs that already have an Application are not
recreated (only missing ApplicationResumeHistory rows are patched in), and
no DELETE is ever issued against Resume or ScreeningResult data.
"""
import asyncio
import logging
from collections import defaultdict
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.job import Job
from app.models.resume import Resume
from app.models.profile import CandidateProfile
from app.models.screening import ScreeningResult
from app.models.candidate import Candidate
from app.models.application import Application, ApplicationResumeHistory
from app.models.decision_audit import DecisionAudit

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_candidates_applications")


def normalize_email(email: Optional[str]) -> Optional[str]:
    if not email:
        return None
    normalized = email.strip().lower()
    return normalized or None


async def resolve_candidates(db: AsyncSession) -> int:
    """Step 1: assign resume.candidate_id for every resume that doesn't have one yet."""
    rows = (
        await db.execute(
            select(Resume, CandidateProfile, Job.organization_id)
            .join(Job, Job.id == Resume.job_id)
            .outerjoin(CandidateProfile, CandidateProfile.resume_id == Resume.id)
            .where(Resume.candidate_id.is_(None))
            .order_by(Resume.id)
        )
    ).all()

    if not rows:
        logger.info("Step 1: no resumes need candidate resolution.")
        return 0

    # Seed the email->candidate map from candidates that already exist (from
    # a prior partial run, or from live traffic since Phase 1 shipped), so
    # re-running never creates a duplicate Candidate for the same email.
    # Keyed by (organization_id, email): candidate identity never crosses
    # organizations.
    existing = await db.execute(select(Candidate).where(Candidate.primary_email.isnot(None)))
    email_to_candidate_id: dict[tuple[int, str], int] = {
        (c.organization_id, c.primary_email): c.id for c in existing.scalars().all()
    }

    new_candidates = 0
    for resume, profile, organization_id in rows:
        email = normalize_email(profile.email if profile else None)

        if email and (organization_id, email) in email_to_candidate_id:
            resume.candidate_id = email_to_candidate_id[(organization_id, email)]
            continue

        candidate = Candidate(
            organization_id=organization_id,
            canonical_name=(profile.name if profile else None),
            primary_email=email,
            primary_phone=(profile.phone if profile else None),
        )
        db.add(candidate)
        await db.flush()  # need candidate.id to assign it to the resume
        resume.candidate_id = candidate.id
        if email:
            email_to_candidate_id[(organization_id, email)] = candidate.id
        new_candidates += 1

    await db.commit()
    logger.info(
        "Step 1: resolved candidate_id for %d resumes (%d new Candidate rows, %d matched an existing email).",
        len(rows), new_candidates, len(rows) - new_candidates,
    )
    return len(rows)


async def _backfill_group(db: AsyncSession, candidate_id: int, job_id: int, group: list[Resume]) -> None:
    existing_app = (
        await db.execute(
            select(Application).where(
                Application.candidate_id == candidate_id, Application.job_id == job_id
            )
        )
    ).scalar_one_or_none()

    resume_ids = [r.id for r in group]

    if existing_app is not None:
        # Re-run: don't recreate the Application or re-seed its decision
        # history - just make sure every resume in the group is represented
        # in ApplicationResumeHistory (covers an interrupted prior run).
        existing_history_resume_ids = {
            row[0]
            for row in (
                await db.execute(
                    select(ApplicationResumeHistory.resume_id).where(
                        ApplicationResumeHistory.application_id == existing_app.id
                    )
                )
            ).all()
        }
        for r in group:
            if r.id not in existing_history_resume_ids:
                db.add(ApplicationResumeHistory(
                    application_id=existing_app.id, resume_id=r.id, batch_id=r.batch_id, used_at=r.created_at,
                ))
        return

    # Deterministic current-resume rule: latest created_at, ties broken by highest id.
    current_resume = max(group, key=lambda r: (r.created_at, r.id))

    screening_results = (
        await db.execute(
            select(ScreeningResult)
            .where(ScreeningResult.job_id == job_id, ScreeningResult.resume_id.in_(resume_ids))
            .order_by(ScreeningResult.created_at, ScreeningResult.id)
        )
    ).scalars().all()
    current_result = next((sr for sr in screening_results if sr.resume_id == current_resume.id), None)

    status = current_resume.status or "APPLIED"
    if current_result and current_result.decision:
        status = current_result.decision

    application = Application(
        candidate_id=candidate_id,
        job_id=job_id,
        current_resume_id=current_resume.id,
        batch_id=current_resume.batch_id,
        status=status,
    )
    db.add(application)
    await db.flush()  # need application.id

    for r in group:
        db.add(ApplicationResumeHistory(
            application_id=application.id, resume_id=r.id, batch_id=r.batch_id, used_at=r.created_at,
        ))

    # Preserve every historical screening result as a DecisionAudit entry,
    # in chronological order, regardless of which resume ends up "current".
    prev = None
    for sr in screening_results:
        db.add(DecisionAudit(
            application_id=application.id,
            event_type="AI_SCREEN" if prev is None else "AI_RESCREEN",
            actor_type="SYSTEM",
            actor_id=None,
            old_decision=prev.decision if prev else None,
            new_decision=sr.decision,
            old_score=prev.score if prev else None,
            new_score=sr.score,
            reason="Backfilled from pre-Application screening_results history.",
            created_at=sr.created_at,
        ))
        prev = sr

    # The one "live" link: only the result belonging to the chosen current
    # resume becomes the Application's authoritative ScreeningResult.
    if current_result is not None:
        current_result.application_id = application.id


async def backfill_applications(db: AsyncSession) -> None:
    """Step 2: group resolved resumes by (candidate_id, job_id), one job at a time."""
    job_ids = [row[0] for row in (await db.execute(select(Resume.job_id).distinct())).all()]
    logger.info("Step 2: backfilling applications across %d jobs.", len(job_ids))

    for job_id in job_ids:
        resumes = (
            await db.execute(
                select(Resume).where(Resume.job_id == job_id).order_by(Resume.created_at, Resume.id)
            )
        ).scalars().all()

        groups: dict[int, list[Resume]] = defaultdict(list)
        for r in resumes:
            groups[r.candidate_id].append(r)

        for candidate_id, group in groups.items():
            await _backfill_group(db, candidate_id, job_id, group)

        await db.commit()

    logger.info("Step 2: done.")


async def print_summary(db: AsyncSession) -> None:
    from sqlalchemy import func as sa_func

    unresolved_resumes = (
        await db.execute(select(sa_func.count()).select_from(Resume).where(Resume.candidate_id.is_(None)))
    ).scalar()
    total_candidates = (await db.execute(select(sa_func.count()).select_from(Candidate))).scalar()
    total_applications = (await db.execute(select(sa_func.count()).select_from(Application))).scalar()
    total_history = (await db.execute(select(sa_func.count()).select_from(ApplicationResumeHistory))).scalar()
    total_audits = (await db.execute(select(sa_func.count()).select_from(DecisionAudit))).scalar()
    linked_results = (
        await db.execute(
            select(sa_func.count()).select_from(ScreeningResult).where(ScreeningResult.application_id.isnot(None))
        )
    ).scalar()

    logger.info(
        "Summary: candidates=%d applications=%d resume_history_rows=%d decision_audits=%d "
        "screening_results_linked=%d resumes_without_candidate=%d",
        total_candidates, total_applications, total_history, total_audits, linked_results, unresolved_resumes,
    )


async def main() -> None:
    async with AsyncSessionLocal() as db:
        await resolve_candidates(db)
        await backfill_applications(db)
        await print_summary(db)


if __name__ == "__main__":
    asyncio.run(main())
