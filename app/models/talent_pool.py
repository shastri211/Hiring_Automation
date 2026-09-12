from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.db.base import Base


class TalentPoolEntry(Base):
    __tablename__ = "talent_pool_entries"

    id = Column(Integer, primary_key=True, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id"), nullable=False, unique=True, index=True)
    added_from_job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True, index=True)

    tags = Column(JSONB, nullable=False, default=list, server_default="[]")
    notes = Column(Text, nullable=True)

    added_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
