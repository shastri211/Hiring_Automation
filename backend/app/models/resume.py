from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index, UniqueConstraint, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

class Resume(Base):
    __tablename__ = "resumes"
    __table_args__ = (
        # Enforces per-job dedup at the DB level so two concurrent upload
        # requests for the same file can't both pass the app-level
        # check-then-insert race in app/api/resumes.py.
        UniqueConstraint("job_id", "file_hash", name="uq_resumes_job_id_file_hash"),
        Index("ix_resumes_unenqueued", "created_at", postgresql_where=text("enqueued_at IS NULL")),
    )

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("screening_batches.id"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    # Nullable during the Phase 1 rollout: backfilled by
    # scripts/backfill_candidates_applications.py for existing rows, and set
    # at upload time going forward. Will move to NOT NULL once resume
    # ingestion is cut over to write it directly (see Application).
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=True, index=True)

    filename = Column(String(255), nullable=False)
    file_hash = Column(String(64), nullable=False, index=True) # For duplicate detection
    storage_key = Column(String(255), nullable=False) # Path in local/S3 storage

    status = Column(String(50), default="UPLOADED") # UPLOADED, PROCESSING, READY, FAILED
    workflow_stage = Column(String(50), default="UPLOADED") # Track exact agentic step
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    # Recruiter uploads: set once Redis confirmed the process_resume message
    # (not "processed" - that's status/workflow_stage). NULL means enqueue
    # was never confirmed; resume_intake.requeue_unenqueued_uploads
    # re-enqueues such rows. Public applications track this on
    # PublicApplicationSubmission.enqueued_at instead.
    enqueued_at = Column(DateTime(timezone=True), nullable=True)

    extracted_text = Column(String, nullable=True)
    error_message = Column(String, nullable=True)

    profile = relationship("CandidateProfile", back_populates="resume", uselist=False)

