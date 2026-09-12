from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.sql import func
from app.db.base import Base

class Interview(Base):
    __tablename__ = "interviews"
    __table_args__ = (UniqueConstraint('job_id', 'resume_id', name='uq_interview_job_resume'),)

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id"), nullable=False, index=True)

    status = Column(String(50), default="PENDING") # PENDING, SCHEDULED, COMPLETED, FAILED
    transcript = Column(Text, nullable=True)
    evaluation = Column(JSON, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
