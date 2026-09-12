from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime

class EmailTemplateBase(BaseModel):
    name: str
    subject: str
    body_content: str

class EmailTemplateCreate(EmailTemplateBase):
    pass

class EmailTemplateUpdate(BaseModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    body_content: Optional[str] = None

class EmailTemplateResponse(EmailTemplateBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class EmailMessageResponse(BaseModel):
    id: int
    job_id: int
    resume_id: int
    template_id: Optional[int] = None
    subject: str
    body_content: str
    status: str
    provider_message_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    sent_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class BulkEmailRequest(BaseModel):
    resume_ids: List[int]
    template_id: int


class EmailMessageGlobalResponse(EmailMessageResponse):
    job_title: Optional[str] = None
    candidate_name: Optional[str] = None


class PaginatedEmailMessageResponse(BaseModel):
    items: List[EmailMessageGlobalResponse]
    total: int
    page: int
    page_size: int
