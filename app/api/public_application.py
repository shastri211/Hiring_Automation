"""Public, unauthenticated-by-design candidate apply endpoints.

Like app/api/public_interview.py, auth here is possession of an opaque
token (Job.application_token), not identity - there are no candidate
accounts. Closing or rotating a job's link replaces/clears the token, so an
old link simply stops resolving (404, indistinguishable from a token that
never existed). 410 "closed" is only for a *current* token whose job is
paused/archived.

What the candidate types into the form is stored as self-reported,
unverified data (PublicApplicationSubmission) and never enters
CandidateProfile, identity resolution, outreach, or any LLM prompt. Logs
here carry only job/resume ids - never the applicant's name or email.
"""
import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.job import Job
from app.schemas.public_application import PublicApplyResponse, PublicJobResponse
from app.services import public_application, rate_limit

logger = logging.getLogger(__name__)

router = APIRouter()

_RATE_WINDOW_SECONDS = 3600
# Format sanity only (one "@", no whitespace, a dotted domain) - the
# address is self-reported and unverified either way, so this just rejects
# obvious typos without pulling in an email-validation dependency.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


async def _get_job_by_token_or_typed_error(token: str, db: AsyncSession) -> Job:
    job = (await db.execute(select(Job).where(Job.application_token == token))).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail={"reason": "not_found"})
    if job.status != "ACTIVE":
        raise HTTPException(status_code=410, detail={"reason": "closed"})
    return job


async def _enforce_rate_limit(key: str, limit: int) -> None:
    try:
        allowed, retry_after = await rate_limit.check(key, limit, _RATE_WINDOW_SECONDS)
    except rate_limit.RateLimiterUnavailable:
        logger.error("Public apply rate limiter unavailable (Redis unreachable); failing closed.")
        raise HTTPException(status_code=503, detail={"reason": "temporarily_unavailable"})
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={"reason": "rate_limited"},
            headers={"Retry-After": str(retry_after)},
        )


@router.get("/{token}", response_model=PublicJobResponse)
async def get_public_job(token: str, db: AsyncSession = Depends(get_db)):
    job = await _get_job_by_token_or_typed_error(token, db)
    job_profile = job.job_profile if isinstance(job.job_profile, dict) else {}
    return PublicJobResponse(
        title=job.title,
        role_summary=job_profile.get("role_summary"),
        responsibilities=job_profile.get("responsibilities") or [],
        description=job.description,
    )


@router.post("/{token}/apply", response_model=PublicApplyResponse, status_code=status.HTTP_202_ACCEPTED)
async def apply_to_job(
    token: str,
    request: Request,
    file: UploadFile = File(...),
    name: str = Form(...),
    email: str = Form(...),
    phone: Optional[str] = Form(None),
    consent: bool = Form(...),
    # Honeypot: hidden in the real form, so only bots fill it.
    website: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    # 1. Per-IP limit first - needs nothing but the client IP, so it also
    #    bounds token guessing. request.client.host is the direct peer; run
    #    uvicorn with --proxy-headers behind a reverse proxy.
    client_ip = request.client.host if request.client else "unknown"
    await _enforce_rate_limit(
        f"apply:ip:{rate_limit.hash_client_ip(client_ip)}", settings.PUBLIC_APPLY_MAX_PER_IP_PER_HOUR
    )

    # 2. Honeypot: pretend success, store nothing.
    if website:
        return PublicApplyResponse()

    # 3. Resolve the token (404 unknown/closed/rotated, 410 job not ACTIVE).
    job = await _get_job_by_token_or_typed_error(token, db)

    # 4. Per-job limit, keyed on the resolved job - never on a raw token.
    await _enforce_rate_limit(f"apply:job:{job.id}", settings.PUBLIC_APPLY_MAX_PER_JOB_PER_HOUR)

    # 5. Field validation.
    if not consent:
        raise HTTPException(status_code=422, detail={"reason": "consent_required"})
    name = (name or "").strip()
    phone = (phone or "").strip() or None
    if not name or len(name) > 255:
        raise HTTPException(status_code=422, detail={"reason": "invalid_name"})
    email = (email or "").strip()
    if len(email) > 320 or not _EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail={"reason": "invalid_email"})
    if phone is not None and len(phone) > 50:
        raise HTTPException(status_code=422, detail={"reason": "invalid_phone"})

    # 6-7. Store + enqueue (see app/services/public_application.py).
    outcome = await public_application.submit_application(
        db, job=job, file=file, name=name, email=email, phone=phone
    )
    if outcome == "invalid":
        raise HTTPException(
            status_code=400,
            detail={
                "reason": "invalid_file",
                "message": f"Upload a PDF or DOCX resume up to {settings.MAX_RESUME_FILE_SIZE_MB} MB.",
            },
        )
    return PublicApplyResponse()
