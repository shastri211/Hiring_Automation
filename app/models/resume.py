from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

class Resume(Base):
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("screening_batches.id"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    
    filename = Column(String(255), nullable=False)
    file_hash = Column(String(64), nullable=False, index=True) # For duplicate detection
    storage_key = Column(String(255), nullable=False) # Path in local/S3 storage
    
    status = Column(String(50), default="UPLOADED") # UPLOADED, PROCESSING, READY, FAILED
    workflow_stage = Column(String(50), default="UPLOADED") # Track exact agentic step
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    extracted_text = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    
    profile = relationship("CandidateProfile", back_populates="resume", uselist=False)

