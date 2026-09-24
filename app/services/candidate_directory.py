import re
from typing import Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.resume import Resume
from app.models.job import Job
from app.models.profile import CandidateProfile
from app.models.candidate import Candidate
from app.models.application import Application

_EMAIL_LOCAL_PART_SPLIT = re.compile(r"[._+\-]+")


def _derive_name_from_email(email: Optional[str]) -> Optional[str]:
    """Best-effort display name from an email's local part, e.g.
    'jane.doe+resumes@example.com' -> 'Jane Doe'. Used only when neither the
    candidate's canonical_name nor this resume's extracted profile name are
    available - a step up from falling straight to the raw filename."""
    if not email or "@" not in email:
        return None
    local_part = email.split("@", 1)[0]
    words = [w for w in _EMAIL_LOCAL_PART_SPLIT.split(local_part) if w]
    if not words:
        return None
    return " ".join(w.capitalize() for w in words)


async def get_candidate_summaries(db: AsyncSession, resume_ids: List[int]) -> Dict[int, dict]:
    """Batched candidate-identity resolution shared across every consumer
    that needs a resume's display name (app/api/candidates.py, jobs.py,
    talent_pool.py) - the single place this logic lives, replacing what
    used to be independently duplicated at each call site.

    Fallback chain for display_name (Phase 6):
      1. Candidate.canonical_name (HR override, or the name it was auto-
         seeded with at identity resolution time)
      2. this resume's own CandidateProfile.name
      3. a best-effort name derived from the candidate's/profile's email
      4. the resume's filename, minus extension

    Resolves through Candidate.merged_into_id so a resume whose stored
    candidate_id points at an since-absorbed candidate still reports the
    canonical one - callers never need to think about merges themselves.

    Returns {resume_id: {display_name, candidate_id (canonical, or None),
    applications_count (across all of that candidate's jobs, or None),
    email, phone, job_id, job_title}}.

    Every step here is a single batched query over all of resume_ids (or
    the distinct candidate/application ids derived from them) - no query
    is issued per resume or per candidate.
    """
    if not resume_ids:
        return {}

    rows = (
        await db.execute(
            select(
                Resume.id.label("resume_id"),
                Resume.filename,
                Resume.candidate_id,
                Job.id.label("job_id"),
                Job.title.label("job_title"),
                CandidateProfile.name.label("profile_name"),
                CandidateProfile.email.label("profile_email"),
                CandidateProfile.phone.label("profile_phone"),
            )
            .select_from(Resume)
            .join(Job, Job.id == Resume.job_id)
            .outerjoin(CandidateProfile, CandidateProfile.resume_id == Resume.id)
            .where(Resume.id.in_(resume_ids))
        )
    ).all()

    raw_candidate_ids = {r.candidate_id for r in rows if r.candidate_id is not None}

    # One self-join resolves every distinct candidate_id referenced by
    # these resumes to its canonical id/name/email at once. Merge chains
    # are always at most one hop (see app/services/candidate_identity.py),
    # so the merge target (c2, when present) is always the canonical row.
    canonical_id_by_raw_id: Dict[int, int] = {}
    canonical_name_by_id: Dict[int, Optional[str]] = {}
    canonical_email_by_id: Dict[int, Optional[str]] = {}
    if raw_candidate_ids:
        c1 = aliased(Candidate)
        c2 = aliased(Candidate)
        crows = (
            await db.execute(
                select(
                    c1.id.label("raw_id"),
                    func.coalesce(c2.id, c1.id).label("canonical_id"),
                    func.coalesce(c2.canonical_name, c1.canonical_name).label("canonical_name"),
                    func.coalesce(c2.primary_email, c1.primary_email).label("canonical_email"),
                )
                .select_from(c1)
                .outerjoin(c2, c1.merged_into_id == c2.id)
                .where(c1.id.in_(raw_candidate_ids))
            )
        ).all()
        for r in crows:
            canonical_id_by_raw_id[r.raw_id] = r.canonical_id
            canonical_name_by_id[r.canonical_id] = r.canonical_name
            canonical_email_by_id[r.canonical_id] = r.canonical_email

    canonical_ids = set(canonical_id_by_raw_id.values())
    applications_count_by_candidate_id: Dict[int, int] = {}
    if canonical_ids:
        arows = (
            await db.execute(
                select(Application.candidate_id, func.count(Application.id))
                .where(Application.candidate_id.in_(canonical_ids))
                .group_by(Application.candidate_id)
            )
        ).all()
        applications_count_by_candidate_id = {cid: cnt for cid, cnt in arows}

    summaries: Dict[int, dict] = {}
    for row in rows:
        canonical_id = canonical_id_by_raw_id.get(row.candidate_id) if row.candidate_id is not None else None
        canonical_name = canonical_name_by_id.get(canonical_id) if canonical_id is not None else None
        canonical_email = canonical_email_by_id.get(canonical_id) if canonical_id is not None else None

        display_name = (
            canonical_name
            or row.profile_name
            or _derive_name_from_email(canonical_email or row.profile_email)
            or (row.filename.rsplit(".", 1)[0] if row.filename else f"Resume #{row.resume_id}")
        )

        summaries[row.resume_id] = {
            "display_name": display_name,
            # Raw extracted name (unchanged meaning from before Phase 6) -
            # kept distinct from display_name for any consumer that wants
            # specifically "what this resume's own extraction said", e.g.
            # GlobalScreeningResultResponse.candidate_name.
            "profile_name": row.profile_name,
            "candidate_id": canonical_id,
            "applications_count": (
                applications_count_by_candidate_id.get(canonical_id, 0) if canonical_id is not None else None
            ),
            "email": row.profile_email,
            "phone": row.profile_phone,
            "job_id": row.job_id,
            "job_title": row.job_title,
        }

    return summaries
