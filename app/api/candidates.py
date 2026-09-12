from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.db.session import get_db
from app.models.job import Job
from app.models.resume import Resume
from app.models.profile import CandidateProfile
from app.models.screening import ScreeningResult
from app.schemas.screening import (
    PaginatedGlobalScreeningResultResponse,
    GlobalScreeningResultResponse,
    ScreeningResultResponse
)

router = APIRouter()

@router.get("/", response_model=PaginatedGlobalScreeningResultResponse)
async def get_global_candidates(
    decision: Optional[str] = Query(None, description="SHORTLIST | REVIEW | REJECT"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    # Base query joining necessary tables
    query = (
        select(
            ScreeningResult,
            Job.title.label("job_title"),
            CandidateProfile.name.label("candidate_name"),
            Resume.filename,
            Resume.status.label("resume_status"),
            Resume.error_message,
            Resume.id.label("resume_id"),
            Job.id.label("job_id"),
        )
        .select_from(Resume)
        .join(Job, Job.id == Resume.job_id)
        .outerjoin(ScreeningResult, (ScreeningResult.resume_id == Resume.id) & (ScreeningResult.job_id == Job.id))
        .outerjoin(CandidateProfile, CandidateProfile.resume_id == Resume.id)
    )

    if decision:
        if decision.upper() == "NULL" or decision == "":
            query = query.where(ScreeningResult.decision.is_(None))
        else:
            query = query.where(ScreeningResult.decision == decision.upper())

    # Count total
    count_query = select(func.count()).select_from(
        query.with_only_columns(Resume.id).order_by(None).subquery()
    )
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    # Pagination and sorting
    query = query.order_by(ScreeningResult.score.desc().nulls_last())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    rows = result.all()

    items = []
    for row in rows:
        screening_res = row[0]
        job_title = row[1]
        candidate_name = row[2]
        filename = row[3]
        resume_status = row[4]
        error_message = row[5]
        resume_id = row[6]
        job_id = row[7]
        
        display_name = candidate_name if candidate_name else (filename.rsplit('.', 1)[0] if filename else f"Resume #{resume_id}")

        base_item = ScreeningResultResponse(
            id=screening_res.id if screening_res else None,
            job_id=job_id,
            resume_id=resume_id,
            score=screening_res.score if screening_res else None,
            semantic_score=screening_res.semantic_score if screening_res else None,
            strengths=screening_res.strengths if screening_res else None,
            gaps=screening_res.gaps if screening_res else None,
            evidence=screening_res.evidence if screening_res else None,
            decision=screening_res.decision if screening_res else None,
            notes=screening_res.notes if screening_res else None,
            created_at=screening_res.created_at if screening_res else None,
            status=resume_status,
            error_message=error_message,
            display_name=display_name
        )
        data = base_item.model_dump()
        data["job_title"] = job_title
        data["candidate_name"] = candidate_name
        item = GlobalScreeningResultResponse.model_validate(data)
        items.append(item)

    return PaginatedGlobalScreeningResultResponse(
        items=items, total=total, page=page, page_size=page_size
    )
