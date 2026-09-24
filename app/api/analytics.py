from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.analytics import (
    FunnelResponse,
    DecisionBreakdownResponse,
    ThroughputResponse,
    TimeInStageResponse,
    JobVolumeResponse,
)
from app.services.analytics import analytics_service
from app.services import tenancy
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()


async def _org_and_job(db: AsyncSession, current_user: User, job_id: Optional[int]) -> int:
    """The caller's organization; a job_id filter must be one of its jobs
    (404 otherwise, never another organization's numbers)."""
    if job_id is not None:
        await tenancy.get_job_for_org_or_404(db, job_id, current_user.organization_id)
    return current_user.organization_id


@router.get("/funnel", response_model=FunnelResponse)
async def get_funnel(
    job_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = await _org_and_job(db, current_user, job_id)
    return await analytics_service.funnel(db, organization_id=org_id, job_id=job_id)


@router.get("/decisions", response_model=DecisionBreakdownResponse)
async def get_decisions(
    job_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = await _org_and_job(db, current_user, job_id)
    return await analytics_service.decision_breakdown(db, organization_id=org_id, job_id=job_id)


@router.get("/throughput", response_model=ThroughputResponse)
async def get_throughput(
    days: int = Query(30, ge=1, le=365),
    job_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = await _org_and_job(db, current_user, job_id)
    return await analytics_service.throughput(db, organization_id=org_id, days=days, job_id=job_id)


@router.get("/time-in-stage", response_model=TimeInStageResponse)
async def get_time_in_stage(
    job_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = await _org_and_job(db, current_user, job_id)
    return await analytics_service.time_in_stage(db, organization_id=org_id, job_id=job_id)


@router.get("/job-volume", response_model=JobVolumeResponse)
async def get_job_volume(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    return await analytics_service.job_volume(db, organization_id=current_user.organization_id)
