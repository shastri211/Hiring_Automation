import base64
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.config import settings
from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.resume import Resume
from app.models.user import User
from app.services.interview import interview_adapter
from app.schemas.integration import (
    InterviewTriggerRequest,
    InterviewStatusRequest,
    InterviewTranscriptRequest,
    InterviewEvaluationRequest,
    IntegrationResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


async def verify_dograh_webhook(request: Request) -> None:
    """Verify inbound Dograh webhook requests per DOGRAH_WEBHOOK_AUTH_TYPE.

    Implements all 5 real Dograh auth types confirmed against
    docs/developer/webhooks.mdx and api/enums.py in the Dograh source:
    none | api_key | bearer_token | basic_auth | custom_header.

    api_key/custom_header both collapse to "does the configured header equal
    the configured secret" - they differ only in which header name an
    operator configures (DOGRAH_WEBHOOK_HEADER_NAME), so they share this one
    code path rather than being read via a fixed FastAPI Header() alias
    (which can't be config-driven).
    """
    auth_type = (settings.DOGRAH_WEBHOOK_AUTH_TYPE or "none").lower()
    secret = settings.DOGRAH_WEBHOOK_SECRET or ""

    if auth_type == "none":
        return

    if auth_type == "basic_auth":
        authorization = request.headers.get("authorization", "")
        if not authorization.startswith("Basic "):
            raise HTTPException(status_code=401, detail="Missing or invalid Basic auth")
        try:
            decoded = base64.b64decode(authorization[len("Basic "):]).decode("utf-8")
        except Exception:
            raise HTTPException(status_code=401, detail="Malformed Basic auth header")
        if decoded != secret:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return

    if auth_type == "bearer_token":
        authorization = request.headers.get("authorization", "")
        if authorization != f"Bearer {secret}":
            raise HTTPException(status_code=401, detail="Invalid or missing bearer token")
        return

    if auth_type in ("api_key", "custom_header"):
        header_name = settings.DOGRAH_WEBHOOK_HEADER_NAME or "X-API-Key"
        value = request.headers.get(header_name)
        if value != secret or not secret:
            raise HTTPException(status_code=401, detail="Invalid or missing webhook credentials")
        return

    logger.warning("Unknown DOGRAH_WEBHOOK_AUTH_TYPE=%r; rejecting webhook request.", auth_type)
    raise HTTPException(status_code=401, detail="Webhook authentication misconfigured")

async def validate_ownership(job_id: int, resume_id: int, db: AsyncSession):
    """
    Validates that the given resume_id exists and is associated with the job_id.
    Raises a 404 HTTPException if the ownership is invalid.
    """
    resume_res = await db.execute(
        select(Resume).where(Resume.id == resume_id, Resume.job_id == job_id)
    )
    resume = resume_res.scalar_one_or_none()
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found for this job"
        )
    return resume

@router.post("/interview/trigger", response_model=IntegrationResponse)
async def trigger_interview(
    req: InterviewTriggerRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await validate_ownership(req.job_id, req.resume_id, db)
    success = await interview_adapter.trigger_interview(req.resume_id, req.job_id)
    if success:
        return IntegrationResponse(success=True, message="Interview triggered successfully")
    # Actually, trigger_interview currently always returns True.
    # In case it changes to return False:
    raise HTTPException(status_code=400, detail="Failed to trigger interview")


@router.post(
    "/interview/status",
    response_model=IntegrationResponse,
    dependencies=[Depends(verify_dograh_webhook)],
)
async def update_interview_status(
    req: InterviewStatusRequest, db: AsyncSession = Depends(get_db)
):
    await validate_ownership(req.job_id, req.resume_id, db)
    success = await interview_adapter.receive_interview_status(req.resume_id, req.job_id, req.status)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview not found for this candidate"
        )
    return IntegrationResponse(success=True, message="Interview status updated")


@router.post(
    "/interview/transcript",
    response_model=IntegrationResponse,
    dependencies=[Depends(verify_dograh_webhook)],
)
async def receive_interview_transcript(
    req: InterviewTranscriptRequest, db: AsyncSession = Depends(get_db)
):
    await validate_ownership(req.job_id, req.resume_id, db)
    success = await interview_adapter.receive_transcript(req.resume_id, req.job_id, req.transcript)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview not found for this candidate"
        )
    return IntegrationResponse(success=True, message="Interview transcript updated")


@router.post(
    "/interview/evaluation",
    response_model=IntegrationResponse,
    dependencies=[Depends(verify_dograh_webhook)],
)
async def receive_interview_evaluation(
    req: InterviewEvaluationRequest, db: AsyncSession = Depends(get_db)
):
    await validate_ownership(req.job_id, req.resume_id, db)
    success = await interview_adapter.receive_evaluation(req.resume_id, req.job_id, req.evaluation_data)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview not found for this candidate"
        )
    return IntegrationResponse(success=True, message="Interview evaluation updated")
