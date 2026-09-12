from pydantic import BaseModel, ConfigDict
from typing import Optional, Any, List
from datetime import datetime


class GlobalInterviewResponse(BaseModel):
    id: int
    job_id: int
    resume_id: int
    status: str
    transcript: Optional[str] = None
    evaluation: Optional[Any] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    job_title: str
    candidate_name: Optional[str] = None
    resume_filename: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedGlobalInterviewResponse(BaseModel):
    items: List[GlobalInterviewResponse]
    total: int
    page: int
    page_size: int
