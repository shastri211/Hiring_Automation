from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey, Float, UniqueConstraint
from sqlalchemy.sql import func
from app.db.base import Base

class ScreeningResult(Base):
    __tablename__ = "screening_results"
    __table_args__ = (
        UniqueConstraint("job_id", "resume_id", name="uq_screening_job_resume"),
    )

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id"), nullable=False, index=True)

    score = Column(Float, nullable=True)
    semantic_score = Column(Float, nullable=True)
    strengths = Column(JSON, nullable=True)
    gaps = Column(JSON, nullable=True)
    evidence = Column(JSON, nullable=True)
    decision = Column(String(50), nullable=True)  # SHORTLIST / REVIEW / REJECT
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
