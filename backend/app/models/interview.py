from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.sql import func
from app.db.base import Base

class Interview(Base):
    __tablename__ = "interviews"
    __table_args__ = (UniqueConstraint('job_id', 'resume_id', name='uq_interview_job_resume'),)

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id"), nullable=False, index=True)

    # PENDING, SCHEDULED, IN_PROGRESS, COMPLETED, FAILED, RESCHEDULE_PENDING,
    # NO_SHOW, DECLINED - see app/services/interview.py for the state machine.
    status = Column(String(50), default="PENDING")
    transcript = Column(Text, nullable=True)
    evaluation = Column(JSON, nullable=True)
    # Latest-attempt-only classified outcome (verbatim call_disposition, or
    # "manual_decline"), overwritten on each new webhook - not a history of
    # every past attempt's outcome.
    outcome = Column(String(50), nullable=True)

    # Provider integration fields (A10 - Dograh browser/web interview).
    provider = Column(String(50), nullable=True)  # e.g. "dograh"
    provider_run_id = Column(String(100), nullable=True)  # Dograh workflow_run_id, filled in once the webhook/resync arrives
    # Which retry_count generation provider_run_id belongs to - the
    # attempt-generation fence in receive_evaluation/trigger_interview.
    # workflow_run_id alone can't detect "a retry has since superseded this
    # run", since the new run's id doesn't exist until that attempt's own
    # first webhook arrives.
    provider_run_attempt = Column(Integer, nullable=True)
    public_token = Column(String(64), unique=True, index=True, nullable=True)  # our own opaque candidate-facing link token
    link_expires_at = Column(DateTime(timezone=True), nullable=True)
    transcript_url = Column(String, nullable=True)
    recording_url = Column(String, nullable=True)
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    retry_count = Column(Integer, nullable=False, default=0, server_default="0")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
