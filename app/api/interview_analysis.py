from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.interview_analysis import (
    InterviewAnalysisSummaryResponse,
    PaginatedInterviewAnalysisResponse,
)
from app.services.interview_analysis import interview_analysis_service

router = APIRouter()


@router.get("/summary", response_model=InterviewAnalysisSummaryResponse)
async def get_interview_analysis_summary(
    job_id: Optional[int] = Query(None), db: AsyncSession = Depends(get_db)
):
    return await interview_analysis_service.summary(db, job_id=job_id)


@router.get("/", response_model=PaginatedInterviewAnalysisResponse)
async def list_interview_analysis(
    job_id: Optional[int] = Query(None),
    disposition: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    items, total = await interview_analysis_service.list_interviews(
        db, job_id=job_id, disposition=disposition, page=page, page_size=page_size
    )
    return PaginatedInterviewAnalysisResponse(items=items, total=total, page=page, page_size=page_size)
