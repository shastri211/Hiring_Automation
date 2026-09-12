from pydantic import BaseModel, ConfigDict, computed_field
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

    provider: Optional[str] = None
    provider_run_id: Optional[str] = None
    public_token: Optional[str] = None
    link_expires_at: Optional[datetime] = None
    transcript_url: Optional[str] = None
    recording_url: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    job_title: str
    candidate_name: Optional[str] = None
    resume_filename: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

    @computed_field  # type: ignore[misc]
    @property
    def interview_link(self) -> Optional[str]:
        if not self.public_token:
            return None
        from app.core.config import settings

        if not settings.PUBLIC_APP_BASE_URL:
            return None
        return f"{settings.PUBLIC_APP_BASE_URL}/interview-room/{self.public_token}"


class PaginatedGlobalInterviewResponse(BaseModel):
    items: List[GlobalInterviewResponse]
    total: int
    page: int
    page_size: int
