from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    job_profile = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    status = Column(String(50), default="ACTIVE") # ACTIVE, PAUSED, ARCHIVED

    embedding_profile = Column(String(255), nullable=True) # E.g., 'gemini-embedding-2'
    embedding_status = Column(String(50), nullable=True, default="READY") # READY, MIGRATING, FAILED

    # Opaque token for the public candidate apply link (/apply/{token}).
    # NULL = applications closed. Rotating replaces it, so an old link
    # simply stops resolving (404) - see app/api/public_application.py.
    application_token = Column(String(64), nullable=True, unique=True, index=True)

    screening_batches = relationship(
        "ScreeningBatch",
        back_populates="job",
        cascade="all, delete-orphan",
    )