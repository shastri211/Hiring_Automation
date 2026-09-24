from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class ScreeningBatch(Base):
    __tablename__ = "screening_batches"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)

    status = Column(String(50), default="CREATED")
    # UPLOAD (Resume rows point at this batch via batch_id - total_resumes
    # is a snapshot of an actual upload and can be recomputed live from
    # those rows) vs SCREEN (a screen-job trigger batch - see
    # app/services/screening_trigger.py - which never has any Resume row
    # pointing at it; total_resumes is assigned directly there and must be
    # trusted as-is).
    batch_type = Column(String(20), nullable=False, default="UPLOAD", server_default="UPLOAD")
    total_resumes = Column(Integer, nullable=False, default=0)
    processed = Column(Integer, nullable=False, default=0)
    failed = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    job = relationship(
        "Job",
        back_populates="screening_batches",
    )