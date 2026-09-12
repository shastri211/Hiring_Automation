from pydantic import BaseModel
from typing import Dict, Any

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

class IntegrationResponse(BaseModel):
    success: bool
    message: str
