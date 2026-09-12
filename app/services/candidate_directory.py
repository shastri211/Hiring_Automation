from typing import Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resume import Resume
from app.models.job import Job
from app.models.profile import CandidateProfile


async def get_candidate_summaries(db: AsyncSession, resume_ids: List[int]) -> Dict[int, dict]:
    """Batched candidate-identity resolution shared across callers.

    Returns {resume_id: {display_name, email, phone, job_id, job_title}}.
    Centralizes the name-resolution join/fallback logic already duplicated
    across app/api/candidates.py and app/api/jobs.py.
    """
    if not resume_ids:
        return {}

    query = (
        select(
            Resume.id.label("resume_id"),
            Resume.filename,
            Job.id.label("job_id"),
            Job.title.label("job_title"),
            CandidateProfile.name,
            CandidateProfile.email,
            CandidateProfile.phone,
        )
        .select_from(Resume)
        .join(Job, Job.id == Resume.job_id)
        .outerjoin(CandidateProfile, CandidateProfile.resume_id == Resume.id)
        .where(Resume.id.in_(resume_ids))
    )

    result = await db.execute(query)
    rows = result.all()

    summaries: Dict[int, dict] = {}
    for row in rows:
        display_name = row.name if row.name else (
            row.filename.rsplit(".", 1)[0] if row.filename else f"Resume #{row.resume_id}"
        )
        summaries[row.resume_id] = {
            "display_name": display_name,
            "email": row.email,
            "phone": row.phone,
            "job_id": row.job_id,
            "job_title": row.job_title,
        }

    return summaries
