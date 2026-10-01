from pydantic import BaseModel
from typing import Dict, Any, Literal, Optional

class InterviewTriggerRequest(BaseModel):
    job_id: int
    resume_id: int

class InterviewStatusRequest(BaseModel):
    job_id: int
    resume_id: int
    # Mirrors app.services.interview.INTERVIEW_STATUSES - an unknown value
    # is rejected (422) instead of being stored and breaking status logic.
    status: Literal[
        "PENDING", "SCHEDULED", "IN_PROGRESS", "RESCHEDULE_PENDING", "FAILED", "DECLINED", "COMPLETED", "NO_SHOW"
    ]

class InterviewTranscriptRequest(BaseModel):
    job_id: int
    resume_id: int
    transcript: str

class InterviewEvaluationRequest(BaseModel):
    job_id: int
    resume_id: int
    evaluation_data: Dict[str, Any]
    # Dograh always includes call_disposition as a top-level sibling of
    # evaluation_data in the delivered webhook body, not nested inside it
    # (confirmed against a real captured webhook_deliveries.payload row) -
    # without this field it was silently dropped by Pydantic's default
    # extra="ignore" behavior and never reached receive_evaluation.
    call_disposition: Optional[str] = None

class IntegrationResponse(BaseModel):
    success: bool
    message: str
