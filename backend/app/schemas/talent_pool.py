from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime


class TalentPoolEntryCreate(BaseModel):
    resume_id: int
    added_from_job_id: Optional[int] = None
    tags: List[str] = []
    notes: Optional[str] = None


class TalentPoolEntryUpdate(BaseModel):
    tags: Optional[List[str]] = None
    notes: Optional[str] = None


class TalentPoolEntryResponse(BaseModel):
    id: int
    resume_id: int
    added_from_job_id: Optional[int] = None
    tags: List[str] = []
    notes: Optional[str] = None
    added_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    display_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    job_id: Optional[int] = None
    job_title: Optional[str] = None
    # Phase 6: see ScreeningResultResponse for what these represent.
    candidate_id: Optional[int] = None
    applications_count: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedTalentPoolResponse(BaseModel):
    items: List[TalentPoolEntryResponse]
    total: int
    page: int
    page_size: int
