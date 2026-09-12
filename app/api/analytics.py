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

router = APIRouter()


@router.get("/funnel", response_model=FunnelResponse)
async def get_funnel(job_id: Optional[int] = Query(None), db: AsyncSession = Depends(get_db)):
    return await analytics_service.funnel(db, job_id=job_id)


@router.get("/decisions", response_model=DecisionBreakdownResponse)
async def get_decisions(job_id: Optional[int] = Query(None), db: AsyncSession = Depends(get_db)):
    return await analytics_service.decision_breakdown(db, job_id=job_id)


@router.get("/throughput", response_model=ThroughputResponse)
async def get_throughput(
    days: int = Query(30, ge=1, le=365),
    job_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await analytics_service.throughput(db, days=days, job_id=job_id)


@router.get("/time-in-stage", response_model=TimeInStageResponse)
async def get_time_in_stage(job_id: Optional[int] = Query(None), db: AsyncSession = Depends(get_db)):
    return await analytics_service.time_in_stage(db, job_id=job_id)


@router.get("/job-volume", response_model=JobVolumeResponse)
async def get_job_volume(db: AsyncSession = Depends(get_db)):
    return await analytics_service.job_volume(db)
