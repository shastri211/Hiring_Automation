from pydantic import BaseModel
from typing import List, Optional
from datetime import date as date_type


class FunnelResponse(BaseModel):
    job_id: Optional[int] = None
    uploaded: int
    processed: int
    screened: int
    shortlisted: int
    interviewed: int
    completed: int


class DecisionCount(BaseModel):
    decision: Optional[str] = None
    count: int


class DecisionBreakdownResponse(BaseModel):
    items: List[DecisionCount]
    total: int


class ThroughputPoint(BaseModel):
    date: date_type
    count: int


class ThroughputResponse(BaseModel):
    items: List[ThroughputPoint]


class TimeInStageResponse(BaseModel):
    resume_to_screened_seconds_approx: Optional[float] = None
    screened_to_interview_seconds_approx: Optional[float] = None


class JobVolumeItem(BaseModel):
    job_id: int
    job_title: str
    resume_count: int


class JobVolumeResponse(BaseModel):
    items: List[JobVolumeItem]
