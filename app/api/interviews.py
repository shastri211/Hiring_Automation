from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.interview import Interview
from app.models.resume import Resume
from app.models.job import Job
from app.models.profile import CandidateProfile
from app.schemas.interview import GlobalInterviewResponse, PaginatedGlobalInterviewResponse

router = APIRouter()


@router.get("/", response_model=PaginatedGlobalInterviewResponse)
async def get_global_interviews(
    status: Optional[str] = Query(None, description="PENDING | SCHEDULED | COMPLETED | FAILED"),
    job_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(
            Interview,
            Job.title.label("job_title"),
            CandidateProfile.name.label("candidate_name"),
            Resume.filename.label("resume_filename"),
        )
        .select_from(Interview)
        .join(Resume, Resume.id == Interview.resume_id)
        .join(Job, Job.id == Interview.job_id)
        .outerjoin(CandidateProfile, CandidateProfile.resume_id == Interview.resume_id)
    )

    if status:
        query = query.where(Interview.status == status.upper())
    if job_id is not None:
        query = query.where(Interview.job_id == job_id)

    count_query = select(func.count()).select_from(
        query.with_only_columns(Interview.id).order_by(None).subquery()
    )
    total = (await db.execute(count_query)).scalar_one()

    query = query.order_by(Interview.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    rows = (await db.execute(query)).all()

    items = []
    for row in rows:
        interview = row[0]
        data = {
            "id": interview.id,
            "job_id": interview.job_id,
            "resume_id": interview.resume_id,
            "status": interview.status,
            "transcript": interview.transcript,
            "evaluation": interview.evaluation,
            "created_at": interview.created_at,
            "updated_at": interview.updated_at,
            "provider": interview.provider,
            "provider_run_id": interview.provider_run_id,
            "public_token": interview.public_token,
            "link_expires_at": interview.link_expires_at,
            "transcript_url": interview.transcript_url,
            "recording_url": interview.recording_url,
            "scheduled_at": interview.scheduled_at,
            "completed_at": interview.completed_at,
            "job_title": row.job_title,
            "candidate_name": row.candidate_name,
            "resume_filename": row.resume_filename,
        }
        items.append(GlobalInterviewResponse.model_validate(data))

    return PaginatedGlobalInterviewResponse(items=items, total=total, page=page, page_size=page_size)
