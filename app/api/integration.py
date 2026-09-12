from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.models.resume import Resume
from app.services.interview import interview_adapter
from app.schemas.integration import (
    InterviewTriggerRequest,
    InterviewStatusRequest,
    InterviewTranscriptRequest,
    InterviewEvaluationRequest,
    IntegrationResponse,
)

router = APIRouter()

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
    req: InterviewTriggerRequest, db: AsyncSession = Depends(get_db)
):
    await validate_ownership(req.job_id, req.resume_id, db)
    success = await interview_adapter.trigger_interview(req.resume_id, req.job_id)
    if success:
        return IntegrationResponse(success=True, message="Interview triggered successfully")
    # Actually, trigger_interview currently always returns True.
    # In case it changes to return False:
    raise HTTPException(status_code=400, detail="Failed to trigger interview")


@router.post("/interview/status", response_model=IntegrationResponse)
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


@router.post("/interview/transcript", response_model=IntegrationResponse)
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


@router.post("/interview/evaluation", response_model=IntegrationResponse)
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
