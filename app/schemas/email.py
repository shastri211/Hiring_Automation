import re
from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional, List
from datetime import datetime

# Must match the context dict EmailService.render_template substitutes in
# app/services/email.py - any {{tag}} outside this set is never replaced, so
# it would otherwise reach the candidate's inbox as literal unrendered text
# (e.g. a typo'd {{interviewlink}}) with no error or warning anywhere.
_KNOWN_MERGE_FIELDS = {"candidate_name", "job_title", "interview_link"}
_MERGE_FIELD_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def _check_merge_fields(text: Optional[str]) -> Optional[str]:
    if text is None:
        return text
    unknown = sorted({m for m in _MERGE_FIELD_PATTERN.findall(text) if m not in _KNOWN_MERGE_FIELDS})
    if unknown:
        valid = ", ".join("{{" + f + "}}" for f in sorted(_KNOWN_MERGE_FIELDS))
        bad = ", ".join("{{" + u + "}}" for u in unknown)
        raise ValueError(f"Unknown merge field(s) {bad} - valid fields are {valid}.")
    return text


class EmailTemplateBase(BaseModel):
    name: str
    subject: str
    body_content: str

    @field_validator("subject", "body_content")
    @classmethod
    def _validate_merge_fields(cls, v: str) -> str:
        _check_merge_fields(v)
        return v

class EmailTemplateCreate(EmailTemplateBase):
    pass

class EmailTemplateUpdate(BaseModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    body_content: Optional[str] = None

    @field_validator("subject", "body_content")
    @classmethod
    def _validate_merge_fields(cls, v: Optional[str]) -> Optional[str]:
        return _check_merge_fields(v)

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
