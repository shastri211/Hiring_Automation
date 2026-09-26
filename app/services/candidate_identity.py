"""Candidate identity resolution and matching (Phase 2).

Single centralized home for:
  - exact-email auto-linking a Resume to a Candidate
  - placeholder Candidate creation when no email is available
  - phone-exact CandidateMatchSuggestion filing (v1 signal only - never
    auto-merges)
  - Application get-or-create / resume-version-swap bookkeeping
  - reversible Candidate merge/unmerge, and match-suggestion review

Called from app/services/orchestrator.py right after CandidateProfile is
written (Stage 2) - the first point an email/phone is known. Deliberately
does not touch ScreeningResult or DecisionAudit: wiring a version-swapped
resume into a fresh screening pass (and its audit trail) is the next
phase's concern, not this one's.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.candidate import Candidate, CandidateMergeLog, CandidateMatchSuggestion
from app.models.application import Application, ApplicationResumeHistory
from app.models.resume import Resume
from app.models.profile import CandidateProfile
from app.services.tenancy import NotInOrganization

logger = logging.getLogger(__name__)

# Confidence assigned to a phone-exact match suggestion. Fixed for v1 since
# phone-exact is the only signal in play; revisit once name-similarity (or
# other signals) are added and a suggestion can be produced by more than
# one rule at once.
PHONE_MATCH_CONFIDENCE = 0.6

# Defensive cap on merge-redirect chain length. Merges always target an
# already-canonical candidate (see merge_candidates), so a chain should
# never exceed one hop - this just guards against ever looping forever if
# that invariant is somehow violated.
_MAX_MERGE_CHAIN_HOPS = 20


def normalize_email(email: Optional[str]) -> Optional[str]:
    if not email:
        return None
    normalized = email.strip().lower()
    return normalized or None


def normalize_phone(phone: Optional[str]) -> Optional[str]:
    """Digits-only normalization, so '+1 (555) 123-4567' and '5551234567'
    compare equal - a leading US/Canada country code ('1' on an 11-digit
    number) is stripped so both reduce to the same 10-digit form. Empty/
    too-short results are treated as no signal, so a garbled extraction
    fragment (e.g. '123') can never accidentally phone-match two unrelated
    candidates who both happen to have one."""
    if not phone:
        return None
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) < 7:
        return None
    return digits


async def resolve_canonical_candidate_id(db: AsyncSession, candidate_id: int) -> int:
    """Follow Candidate.merged_into_id redirects to the canonical (un-merged)
    candidate. Every read that cares about "this candidate's" resumes,
    applications, screening results, etc. must resolve through this first,
    so a merge is invisible to consumers without moving any data."""
    current_id = candidate_id
    for _ in range(_MAX_MERGE_CHAIN_HOPS):
        candidate = (await db.execute(select(Candidate).where(Candidate.id == current_id))).scalar_one()
        if candidate.merged_into_id is None:
            return current_id
        current_id = candidate.merged_into_id
    logger.error(
        "Candidate merge chain exceeded %d hops starting from %d; returning last-seen id %d.",
        _MAX_MERGE_CHAIN_HOPS, candidate_id, current_id,
    )
    return current_id


async def _find_active_candidate_by_email(
    db: AsyncSession, email: str, organization_id: int
) -> Optional[Candidate]:
    # Scoped exactly like uq_candidates_primary_email_active
    # (organization_id, primary_email): identity never crosses organizations.
    result = await db.execute(
        select(Candidate).where(
            Candidate.organization_id == organization_id,
            Candidate.primary_email == email,
            Candidate.merged_into_id.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def _create_candidate(
    db: AsyncSession,
    *,
    organization_id: int,
    canonical_name: Optional[str],
    primary_email: Optional[str],
    primary_phone: Optional[str],
) -> tuple[Candidate, bool]:
    """Insert a new Candidate. Returns (candidate, created).

    When primary_email is set, this can race another worker profiling a
    different resume with the same new email concurrently - closed by the
    partial unique index on (organization_id, primary_email) WHERE
    merged_into_id IS NULL.
    On IntegrityError, created=False and the row we lost the race to is
    returned instead, mirroring the SAVEPOINT/IntegrityError pattern
    already used for resume file_hash uploads in app/api/resumes.py.
    """
    candidate = Candidate(
        organization_id=organization_id,
        canonical_name=canonical_name,
        primary_email=primary_email,
        primary_phone=primary_phone,
    )

    if primary_email is None:
        db.add(candidate)
        await db.flush()
        return candidate, True

    try:
        async with db.begin_nested():
            db.add(candidate)
            await db.flush()
        return candidate, True
    except IntegrityError:
        existing = await _find_active_candidate_by_email(db, primary_email, organization_id)
        if existing is None:
            # Vanishingly unlikely (the row we collided with would have to
            # have been deleted/merged in the same instant) - surface
            # loudly rather than silently creating an orphaned duplicate.
            raise
        return existing, False


async def _file_phone_match_suggestion(db: AsyncSession, *, resume_id: int, new_candidate: Candidate) -> None:
    """v1 fuzzy signal: exact-normalized-phone match only. Files a PENDING
    suggestion for HR review; never merges automatically.

    Two concurrent uploads (WORKER_CONCURRENCY) with the same new phone
    number would otherwise both run this SELECT under READ COMMITTED before
    either's new Candidate row is committed - neither would see the other,
    so no suggestion is ever filed for either. A transaction-scoped
    Postgres advisory lock keyed by the phone (auto-released at this
    transaction's commit/rollback, so no manual unlock needed) serializes
    the two: whichever runs second blocks until the first commits, then its
    SELECT (a fresh READ COMMITTED snapshot) actually sees it.
    """
    phone = normalize_phone(new_candidate.primary_phone)
    if not phone:
        return

    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:phone))"), {"phone": phone})

    result = await db.execute(
        select(Candidate).where(
            # Suggestions never pair candidates across organizations.
            Candidate.organization_id == new_candidate.organization_id,
            Candidate.primary_phone.isnot(None),
            Candidate.merged_into_id.is_(None),
            Candidate.id != new_candidate.id,
        )
    )
    for other in result.scalars().all():
        if normalize_phone(other.primary_phone) == phone:
            db.add(CandidateMatchSuggestion(
                resume_id=resume_id,
                candidate_a_id=other.id,
                candidate_b_id=new_candidate.id,
                confidence=PHONE_MATCH_CONFIDENCE,
                signals={"phone_match": True},
                status="PENDING",
            ))
            # One suggestion per new candidate is enough for HR to act on -
            # stop at the first match rather than filing one per every
            # phone-sharing candidate found.
            return


async def resolve_candidate_for_resume(
    db: AsyncSession, resume: Resume, profile: CandidateProfile, *, organization_id: int
) -> int:
    """Assigns resume.candidate_id and returns the resolved candidate id.

    - Exact normalized-email match against an existing (non-merged)
      Candidate -> auto-link, full confidence, no review needed.
    - No match (a new email, or no email at all) -> create a new Candidate
      (a genuine placeholder only when there's no email at all); if it has
      a phone that exact-matches an existing candidate's, file a
      CandidateMatchSuggestion for HR review. Never auto-merges.
    """
    if resume.candidate_id is not None:
        return resume.candidate_id  # already resolved (idempotent on reprocessing)

    email = normalize_email(profile.email)

    if email:
        existing = await _find_active_candidate_by_email(db, email, organization_id)
        if existing is not None:
            resolved_id = await resolve_canonical_candidate_id(db, existing.id)
            resume.candidate_id = resolved_id
            return resolved_id

    candidate, created = await _create_candidate(
        db,
        organization_id=organization_id,
        canonical_name=profile.name,
        primary_email=email,
        primary_phone=profile.phone,
    )
    resolved_id = await resolve_canonical_candidate_id(db, candidate.id)
    resume.candidate_id = resolved_id

    if created:
        await _file_phone_match_suggestion(db, resume_id=resume.id, new_candidate=candidate)

    return resolved_id


async def get_or_create_application(
    db: AsyncSession, *, candidate_id: int, job_id: int, resume: Resume
) -> tuple[Application, bool]:
    """Ensures exactly one Application exists for (candidate_id, job_id).

    A different resume arriving for an already-existing (candidate, job)
    pair is a resume-version update, never a second Application: the
    outgoing current_resume is preserved via ApplicationResumeHistory and
    the pointer is swapped.

    Returns (application, is_version_swap) - the caller (the orchestrator)
    uses is_version_swap to trigger a fresh screening pass once this resume
    reaches READY (Phase 4: app/services/screening_trigger.py). A first-time
    Application is not a swap - whatever already triggers initial screening
    for a new upload is untouched.
    """
    existing = (
        await db.execute(
            select(Application).where(Application.candidate_id == candidate_id, Application.job_id == job_id)
        )
    ).scalar_one_or_none()

    if existing is None:
        application = Application(
            candidate_id=candidate_id,
            job_id=job_id,
            current_resume_id=resume.id,
            batch_id=resume.batch_id,
            status="APPLIED",
        )
        db.add(application)
        await db.flush()
        db.add(ApplicationResumeHistory(application_id=application.id, resume_id=resume.id, batch_id=resume.batch_id))
        return application, False

    if existing.current_resume_id != resume.id:
        db.add(ApplicationResumeHistory(application_id=existing.id, resume_id=resume.id, batch_id=resume.batch_id))
        existing.current_resume_id = resume.id
        return existing, True

    return existing, False


async def _require_candidates_in_org(db: AsyncSession, candidate_ids, organization_id: int) -> None:
    """Every id must be a candidate of `organization_id`; otherwise
    NotInOrganization (missing and another tenant's alike)."""
    wanted = set(candidate_ids)
    found = set(
        (
            await db.execute(
                select(Candidate.id).where(Candidate.id.in_(wanted), Candidate.organization_id == organization_id)
            )
        ).scalars().all()
    )
    if found != wanted:
        raise NotInOrganization("Candidate not found")


async def merge_candidates(
    db: AsyncSession, *, absorbed_id: int, into_id: int, merged_by: int, organization_id: int
) -> CandidateMergeLog:
    """HR-initiated merge. Pure redirect - no Resume/Application row is ever
    touched, which is what makes unmerge_candidate a lossless, instant undo.

    Locks both input candidate rows (ascending id order, so two concurrent
    merges can never deadlock waiting on each other) before resolving or
    checking anything. Without this, two opposite-direction merges
    submitted at the same instant - merge(A->B) and merge(B->A), both
    starting from still-canonical A and B - could each read the other side
    as canonical and both commit, leaving a 2-candidate cycle that
    resolve_canonical_candidate_id can only log an error about afterward,
    never prevent.
    """
    # Both inputs must be this organization's candidates (checked before
    # locking anything). Merge redirects only ever point within one
    # organization, so the canonical targets resolved below are too.
    await _require_candidates_in_org(db, {absorbed_id, into_id}, organization_id)

    lock_ids = sorted({absorbed_id, into_id})
    await db.execute(select(Candidate.id).where(Candidate.id.in_(lock_ids)).with_for_update())

    canonical_into_id = await resolve_canonical_candidate_id(db, into_id)
    canonical_absorbed_id = await resolve_canonical_candidate_id(db, absorbed_id)

    if canonical_absorbed_id == canonical_into_id:
        raise ValueError("These candidates are already the same (or already merged together).")

    absorbed = (await db.execute(select(Candidate).where(Candidate.id == canonical_absorbed_id))).scalar_one()
    absorbed.merged_into_id = canonical_into_id

    log = CandidateMergeLog(
        absorbed_candidate_id=canonical_absorbed_id,
        into_candidate_id=canonical_into_id,
        merged_by=merged_by,
    )
    db.add(log)
    await db.flush()
    return log


async def unmerge_candidate(
    db: AsyncSession, *, absorbed_id: int, reverted_by: int, organization_id: int
) -> CandidateMergeLog:
    """Reverses the most recent active merge for absorbed_id. Since merges
    never move data, this instantly restores full visibility of the
    absorbed candidate's resumes/applications."""
    await _require_candidates_in_org(db, {absorbed_id}, organization_id)
    log = (
        await db.execute(
            select(CandidateMergeLog)
            .where(CandidateMergeLog.absorbed_candidate_id == absorbed_id, CandidateMergeLog.reverted_at.is_(None))
            .order_by(CandidateMergeLog.merged_at.desc())
        )
    ).scalars().first()
    if log is None:
        raise ValueError("No active merge found for this candidate.")

    absorbed = (await db.execute(select(Candidate).where(Candidate.id == absorbed_id))).scalar_one()
    absorbed.merged_into_id = None

    log.reverted_by = reverted_by
    log.reverted_at = datetime.now(timezone.utc)
    return log


async def _get_suggestion_in_org(db: AsyncSession, suggestion_id: int, organization_id: int) -> CandidateMatchSuggestion:
    """A suggestion only ever pairs candidates of one organization (see
    _file_phone_match_suggestion), so the newer candidate's organization is
    the suggestion's."""
    suggestion = (
        await db.execute(
            select(CandidateMatchSuggestion)
            .join(Candidate, Candidate.id == CandidateMatchSuggestion.candidate_b_id)
            .where(CandidateMatchSuggestion.id == suggestion_id, Candidate.organization_id == organization_id)
        )
    ).scalar_one_or_none()
    if suggestion is None:
        raise NotInOrganization("Match suggestion not found.")
    return suggestion


async def reject_match_suggestion(
    db: AsyncSession, *, suggestion_id: int, reviewed_by: int, organization_id: int
) -> CandidateMatchSuggestion:
    """HR reviewed a suggestion and decided the two candidates are distinct."""
    suggestion = await _get_suggestion_in_org(db, suggestion_id, organization_id)

    suggestion.status = "REJECTED"
    suggestion.reviewed_by = reviewed_by
    suggestion.reviewed_at = datetime.now(timezone.utc)
    return suggestion


async def merge_from_suggestion(
    db: AsyncSession, *, suggestion_id: int, merged_by: int, organization_id: int
) -> CandidateMergeLog:
    """HR confirmed a suggestion: merges the newer candidate (candidate_b,
    the one created for the resume that triggered the suggestion) into the
    pre-existing one (candidate_a)."""
    suggestion = await _get_suggestion_in_org(db, suggestion_id, organization_id)

    log = await merge_candidates(
        db, absorbed_id=suggestion.candidate_b_id, into_id=suggestion.candidate_a_id, merged_by=merged_by,
        organization_id=organization_id,
    )
    suggestion.status = "MERGED"
    suggestion.reviewed_by = merged_by
    suggestion.reviewed_at = datetime.now(timezone.utc)
    return log
