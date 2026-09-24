from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class CandidateResponse(BaseModel):
    id: int
    canonical_name: Optional[str] = None
    primary_email: Optional[str] = None
    primary_phone: Optional[str] = None
    # Mirrors Candidate.merged_into_id (see app/services/candidate_identity.py
    # resolve_canonical_candidate_id) - non-null means this candidate has
    # been merged away and is no longer canonical; merged_into_name is
    # resolved server-side purely for display, never used for identity logic.
    merged_into_id: Optional[int] = None
    merged_into_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CandidateSummary(BaseModel):
    """Minimal candidate identity + volume signal, for reviewing a match
    suggestion or any other place two candidates need to be compared without
    pulling every resume/application row."""

    id: int
    canonical_name: Optional[str] = None
    primary_email: Optional[str] = None
    primary_phone: Optional[str] = None
    applications_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class CandidateNameUpdateRequest(BaseModel):
    # HR override (Phase 6): a plain field edit, not a decision - no audit
    # trail. Blank/whitespace-only clears the override so the fallback
    # chain (profile name / email-derived / filename) takes over again.
    canonical_name: Optional[str] = Field(None, max_length=255)


class CandidateMatchSuggestionResponse(BaseModel):
    id: int
    resume_id: int
    candidate_a_id: int
    candidate_b_id: int
    confidence: float
    signals: Optional[Any] = None
    status: str
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CandidateMatchSuggestionDetailResponse(CandidateMatchSuggestionResponse):
    """GET /candidates/match-suggestions' actual response shape - adds the
    read-only context a reviewer needs (both candidates' identities, and
    where candidate_b's triggering resume came from) without changing the
    suggestion's own fields or review semantics at all. candidate_a is
    always the pre-existing candidate, candidate_b the newer one created for
    resume_id (see candidate_identity._file_phone_match_suggestion) - merging
    a suggestion always absorbs b into a, never the reverse."""

    candidate_a: CandidateSummary
    candidate_b: CandidateSummary
    resume_filename: Optional[str] = None
    job_id: Optional[int] = None
    job_title: Optional[str] = None


class MergeCandidatesRequest(BaseModel):
    absorbed_candidate_id: int
    into_candidate_id: int


class UnmergeCandidateResponse(BaseModel):
    absorbed_candidate_id: int
    into_candidate_id: int
    reverted_at: datetime

    model_config = ConfigDict(from_attributes=True)
