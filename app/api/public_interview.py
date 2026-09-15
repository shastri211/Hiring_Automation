"""Public, unauthenticated-by-design candidate-facing interview room endpoints.

Deliberately outside /integration (which is our own frontend + Dograh
webhooks) - this is the page a candidate opens directly. Auth here is
possession of the opaque `public_token`, not identity. Every lookup is keyed
off that token so a request can never see another candidate's data.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.interview import Interview
from app.models.job import Job
from app.models.profile import CandidateProfile

logger = logging.getLogger(__name__)

router = APIRouter()


async def _get_interview_or_typed_error(token: str, db: AsyncSession) -> Interview:
    result = await db.execute(select(Interview).where(Interview.public_token == token))
    interview = result.scalar_one_or_none()
    if not interview:
        raise HTTPException(status_code=404, detail={"reason": "not_found"})
    if interview.status == "COMPLETED":
        raise HTTPException(status_code=410, detail={"reason": "already_completed"})
    if interview.link_expires_at is not None:
        expires_at = interview.link_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=410, detail={"reason": "expired"})
    return interview


@router.get("/{token}")
async def get_interview_room(token: str, db: AsyncSession = Depends(get_db)):
    interview = await _get_interview_or_typed_error(token, db)

    job_res = await db.execute(select(Job).where(Job.id == interview.job_id))
    job = job_res.scalar_one_or_none()

    profile_res = await db.execute(
        select(CandidateProfile).where(CandidateProfile.resume_id == interview.resume_id)
    )
    profile = profile_res.scalar_one_or_none()

    candidate_name = profile.name if profile and profile.name else "Candidate"
    job_title = job.title if job else ""

    return {
        "candidate_name": candidate_name,
        "job_title": job_title,
        # The widget's <script src> and its own API calls (apiEndpoint) can be
        # different origins on a local self-hosted Dograh with no nginx in
        # front of it - see DOGRAH_WIDGET_BASE_URL in app/core/config.py.
        "dograh_base_url": settings.DOGRAH_BASE_URL,
        "dograh_widget_base_url": settings.DOGRAH_WIDGET_BASE_URL or settings.DOGRAH_BASE_URL,
        "dograh_embed_token": settings.DOGRAH_EMBED_TOKEN,
        "dograh_environment": settings.DOGRAH_ENVIRONMENT,
        "dograh_api_endpoint": settings.DOGRAH_BASE_URL,
        "initial_context": {
            "job_id": interview.job_id,
            "resume_id": interview.resume_id,
            "interview_id": interview.id,
            # Additive fields the screening workflow's prompts reference as
            # {{initial_context.<name>}} - existing keys above are unchanged.
            "candidate_name": candidate_name,
            "candidate_summary": (profile.summary if profile and profile.summary else ""),
            "job_title": job_title,
            "job_requirements": (job.description if job and job.description else ""),
        },
    }


@router.post("/{token}/started")
async def mark_interview_started(token: str, db: AsyncSession = Depends(get_db)):
    interview = await _get_interview_or_typed_error(token, db)
    if interview.status in ("PENDING", "SCHEDULED"):
        interview.status = "IN_PROGRESS"
        await db.commit()
    return {"success": True}
