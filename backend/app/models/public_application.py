from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index, text
from sqlalchemy.sql import func
from app.db.base import Base


class PublicApplicationSubmission(Base):
    """What a candidate typed into the public apply form (app/api/public_application.py).

    Self-reported and unverified - deliberately kept apart from
    CandidateProfile (which only ever holds what was extracted from the
    resume itself) and never fed into identity resolution, outreach, or any
    LLM prompt. One row per Resume row created by a public application.

    `enqueued_at` means "the process_resume queue message was confirmed
    accepted by Redis" - NOT "processing completed" (that is
    Resume.status/workflow_stage). NULL means enqueue was never confirmed;
    the worker's recovery sweep
    (public_application.requeue_unenqueued_applications) re-enqueues such
    rows, which may produce a harmless duplicate message.
    """

    __tablename__ = "public_application_submissions"
    __table_args__ = (
        Index(
            "ix_public_application_submissions_unenqueued",
            "created_at",
            postgresql_where=text("enqueued_at IS NULL"),
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id"), nullable=False, unique=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)

    applicant_name = Column(String(255), nullable=False)
    applicant_email = Column(String(320), nullable=False)
    applicant_phone = Column(String(50), nullable=True)
    consent_at = Column(DateTime(timezone=True), nullable=False)

    # Enqueue confirmed (not processing completed) - see class docstring.
    enqueued_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
