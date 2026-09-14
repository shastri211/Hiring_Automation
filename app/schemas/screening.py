from pydantic import BaseModel, Field, ConfigDict, computed_field
from typing import List, Optional, Any, Literal
from datetime import datetime


class ScreeningResultSchema(BaseModel):
    score: Optional[float] = Field(None, description="Overall fit score out of 100")
    semantic_score: Optional[float] = Field(
        None,
        description="Semantic similarity score from vector retrieval"
    )
    strengths: Optional[List[str]] = None
    gaps: Optional[List[str]] = None
    evidence: Optional[List[str]] = None
    decision: Optional[str] = Field(None, description="SHORTLIST, REVIEW, or REJECT")


class DecisionUpdate(BaseModel):
    decision: Optional[Literal["SHORTLIST", "REVIEW", "REJECT"]] = Field(None, description="SHORTLIST, REVIEW, REJECT, or None")
    notes: Optional[str] = None


class BulkDecisionUpdate(BaseModel):
    resume_ids: List[int]
    decision: Optional[Literal["SHORTLIST", "REVIEW", "REJECT"]] = Field(None, description="SHORTLIST, REVIEW, REJECT, or None")


class ScreeningResultResponse(ScreeningResultSchema):
    id: Optional[int] = None
    job_id: int
    resume_id: int
    created_at: Optional[datetime] = None
    status: Optional[str] = None
    error_message: Optional[str] = None
    display_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedScreeningResultResponse(BaseModel):
    items: List[ScreeningResultResponse]
    total: int
    page: int
    page_size: int


class GlobalScreeningResultResponse(ScreeningResultResponse):
    job_title: str
    candidate_name: Optional[str] = None


class PaginatedGlobalScreeningResultResponse(BaseModel):
    items: List[GlobalScreeningResultResponse]
    total: int
    page: int
    page_size: int


class CandidateProfileDetail(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    summary: Optional[str] = None
    total_experience_years: Optional[float] = None
    education: Optional[Any] = None
    experience: Optional[Any] = None
    skills: Optional[Any] = None
    projects: Optional[Any] = None
    certifications: Optional[Any] = None
    languages: Optional[Any] = None
    achievements: Optional[Any] = None


class InterviewResponse(BaseModel):
    id: int
    job_id: int
    resume_id: int
    status: str
    transcript: Optional[str] = None
    evaluation: Optional[Any] = None

    provider: Optional[str] = None
    provider_run_id: Optional[str] = None
    public_token: Optional[str] = None
    link_expires_at: Optional[datetime] = None
    transcript_url: Optional[str] = None
    recording_url: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

    @computed_field  # type: ignore[misc]
    @property
    def interview_link(self) -> Optional[str]:
        """Full candidate-facing interview room URL, pre-built server-side so
        the frontend's "copy interview link" action never needs to assemble a
        base URL itself. None until trigger_interview has minted a token, or
        if PUBLIC_APP_BASE_URL isn't configured."""
        if not self.public_token:
            return None
        from app.core.config import settings

        if not settings.PUBLIC_APP_BASE_URL:
            return None
        return f"{settings.PUBLIC_APP_BASE_URL}/interview-room/{self.public_token}"


class CandidateDetailResponse(BaseModel):
    resume_id: int
    filename: str
    status: str
    error_message: Optional[str] = None
    profile: Optional[CandidateProfileDetail] = None
    screening: Optional[ScreeningResultResponse] = None
    interview: Optional[InterviewResponse] = None


class BatchProgressDetail(BaseModel):
    batch_id: int
    status: str
    total: int
    processing: int
    completed: int
    failed: int
    shortlisted: int
    review: int
    rejected: int
    pre_screened_out: int = 0


class BatchProgressResponse(BaseModel):
    job_id: int
    batches: List[BatchProgressDetail]


class JobBatchOverviewItem(BaseModel):
    """One row of the cross-job Processing overview (sidebar > Processing).

    A lighter-weight sibling of BatchProgressDetail: counts come straight off
    the ScreeningBatch row (kept in sync by the worker/upload endpoint) rather
    than a live per-status Resume count, so listing every batch across every
    job stays a single query instead of N+1.
    """
    job_id: int
    job_title: str
    job_status: Optional[str] = None
    batch_id: int
    batch_status: str
    total: int
    processed: int
    failed: int
    created_at: Optional[datetime] = None
