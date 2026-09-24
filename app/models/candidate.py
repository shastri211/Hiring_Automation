from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Index, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.db.base import Base


class Candidate(Base):
    """A canonical person, de-duplicated across resumes and job applications.

    Identity is only ever resolved by exact-match signals (normalized email);
    anything less certain becomes a CandidateMatchSuggestion for HR review
    instead of an automatic merge. merged_into_id implements merges as a
    reversible redirect: an absorbed candidate's rows are never rewritten or
    deleted, they're just pointed at the surviving candidate (see
    CandidateMergeLog), so un-merging is just clearing this column.
    """

    __tablename__ = "candidates"
    __table_args__ = (
        # Active (non-merged-away) candidates only - closes the race where
        # two resumes with the same new email, profiled concurrently by
        # different workers, could otherwise each create their own
        # Candidate. See app/services/candidate_identity.py.
        Index(
            "uq_candidates_primary_email_active",
            "primary_email",
            unique=True,
            postgresql_where=text("merged_into_id IS NULL"),
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    canonical_name = Column(String(255), nullable=True)
    primary_email = Column(String(255), nullable=True, index=True)
    primary_phone = Column(String(50), nullable=True, index=True)

    merged_into_id = Column(Integer, ForeignKey("candidates.id", ondelete="RESTRICT"), nullable=True, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class CandidateMergeLog(Base):
    """Audit trail for candidate merges (see Candidate.merged_into_id), so a merge can be reversed."""

    __tablename__ = "candidate_merge_logs"

    id = Column(Integer, primary_key=True, index=True)
    absorbed_candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False, index=True)
    into_candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False, index=True)

    merged_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    merged_at = Column(DateTime(timezone=True), server_default=func.now())

    reverted_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reverted_at = Column(DateTime(timezone=True), nullable=True)


class CandidateMatchSuggestion(Base):
    """A possible-duplicate-candidate flag awaiting HR review.

    Filed for match signals below the exact-email auto-link threshold
    (name/phone/fuzzy similarity). Never auto-merged: status starts PENDING
    and only becomes MERGED/REJECTED via explicit HR action.
    """

    __tablename__ = "candidate_match_suggestions"

    id = Column(Integer, primary_key=True, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id"), nullable=False, index=True)
    candidate_a_id = Column(Integer, ForeignKey("candidates.id"), nullable=False, index=True)
    candidate_b_id = Column(Integer, ForeignKey("candidates.id"), nullable=False, index=True)

    confidence = Column(Float, nullable=False)
    signals = Column(JSONB, nullable=True)

    status = Column(String(50), default="PENDING", index=True)  # PENDING, MERGED, REJECTED
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
