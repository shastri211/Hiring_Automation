from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from app.db.base import Base


class Application(Base):
    """A candidate's application to a job - the (candidate, job) relationship itself.

    Deliberately does not use a resume as its identity: current_resume_id is
    just a pointer to whichever resume currently represents the candidate for
    this job, and can be swapped (see ApplicationResumeHistory) without ever
    creating a second Application row for the same (candidate, job) pair.
    """

    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("candidate_id", "job_id", name="uq_applications_candidate_job"),
    )

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    current_resume_id = Column(Integer, ForeignKey("resumes.id"), nullable=False, index=True)
    batch_id = Column(Integer, ForeignKey("screening_batches.id"), nullable=False, index=True)

    status = Column(String(50), default="APPLIED")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class ApplicationResumeHistory(Base):
    """Every resume that has ever been an Application's current_resume_id.

    Preserves full lineage when the resume behind an application changes -
    nothing is ever deleted, a prior resume is only ever superseded.
    """

    __tablename__ = "application_resume_history"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id"), nullable=False, index=True)
    batch_id = Column(Integer, ForeignKey("screening_batches.id"), nullable=True, index=True)

    used_at = Column(DateTime(timezone=True), server_default=func.now())
