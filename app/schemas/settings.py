from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class AppSettingsResponse(BaseModel):
    id: int
    org_name: Optional[str] = None
    min_candidates_to_screen: Optional[int] = None
    max_candidates_to_screen: Optional[int] = None
    semantic_gap_threshold: Optional[float] = None
    auto_email_on_shortlist: bool = False
    shortlist_email_template_id: Optional[int] = None
    auto_email_on_interview_scheduled: bool = False
    interview_scheduled_email_template_id: Optional[int] = None
    email_test_allowlist: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AppSettingsUpdate(BaseModel):
    org_name: Optional[str] = None
    min_candidates_to_screen: Optional[int] = None
    max_candidates_to_screen: Optional[int] = None
    semantic_gap_threshold: Optional[float] = None
    auto_email_on_shortlist: Optional[bool] = None
    shortlist_email_template_id: Optional[int] = None
    auto_email_on_interview_scheduled: Optional[bool] = None
    interview_scheduled_email_template_id: Optional[int] = None
    email_test_allowlist: Optional[str] = None
