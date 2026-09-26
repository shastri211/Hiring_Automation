from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class PublicJobResponse(BaseModel):
    """What an anonymous visitor to /apply/{token} may see about a job.

    Deliberately minimal and separate from JobResponse: no id, status,
    token, job_profile JSON, embedding fields, or timestamps.
    """

    title: str
    role_summary: Optional[str] = None
    responsibilities: List[str] = []
    # Raw JD text - the fallback when a job has no structured profile.
    description: str


class PublicApplyResponse(BaseModel):
    # Always the same generic body for accepted, duplicate and honeypot
    # submissions, so the response never reveals existing records.
    status: str = "received"


class SelfReportedContact(BaseModel):
    """Unverified contact details the candidate typed into the public apply
    form - shown to recruiters as such, never merged into CandidateProfile."""

    name: str
    email: str
    phone: Optional[str] = None
    submitted_at: datetime
