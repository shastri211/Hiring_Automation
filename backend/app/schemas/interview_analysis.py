from pydantic import BaseModel
from typing import Optional, Any, List, Dict
from datetime import datetime


class InterviewAnalysisSummaryResponse(BaseModel):
    job_id: Optional[int] = None
    total_interviews: int
    completed_interviews: int
    completion_rate: float
    avg_call_duration_seconds: Optional[float] = None
    disposition_breakdown: Dict[str, int]


class InterviewAnalysisItem(BaseModel):
    id: int
    job_id: int
    resume_id: int
    status: str
    job_title: str
    candidate_name: Optional[str] = None
    source: str
    workflow_run_id: Optional[str] = None
    call_disposition: str
    gathered_context: Dict[str, Any] = {}
    cost_info: Dict[str, Any] = {}
    user_recording_url: Optional[str] = None
    bot_recording_url: Optional[str] = None
    created_at: Optional[datetime] = None
    # Read directly off Interview.evaluation's flat top-level keys (see
    # app/services/interview.py::_normalize_evaluation_data) - separate from
    # the envelope fields above, which come from parse_evaluation_envelope's
    # legacy/flat call_disposition+duration normalization, not this.
    interview_recommendation: Optional[str] = None
    communication_clarity: Optional[str] = None
    demonstrated_skill_depth: Optional[str] = None


class PaginatedInterviewAnalysisResponse(BaseModel):
    items: List[InterviewAnalysisItem]
    total: int
    page: int
    page_size: int
