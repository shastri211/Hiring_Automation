from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.db.base import Base


class DecisionAudit(Base):
    """Full history of screening decisions/scores for an Application.

    Every automated re-screen (AI_RESCREEN/AI_SCREEN) and every HR override
    (HR_OVERRIDE) is logged here - actor_type/actor_id make the source of
    each change unambiguous. Nothing is collapsed or summarized at write
    time; any grouping of low-value events belongs in the UI, not here.
    """

    __tablename__ = "decision_audits"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False, index=True)

    event_type = Column(String(50), nullable=False, index=True)  # AI_SCREEN, AI_RESCREEN, HR_OVERRIDE
    actor_type = Column(String(20), nullable=False)  # SYSTEM, HR_USER
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    old_decision = Column(String(50), nullable=True)
    new_decision = Column(String(50), nullable=True)
    old_score = Column(Float, nullable=True)
    new_score = Column(Float, nullable=True)
    reason = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
