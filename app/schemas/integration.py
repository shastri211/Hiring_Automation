from pydantic import BaseModel
from typing import Dict, Any, Optional

class InterviewTriggerRequest(BaseModel):
    job_id: int
    resume_id: int

class InterviewStatusRequest(BaseModel):
    job_id: int
    resume_id: int
    status: str

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
