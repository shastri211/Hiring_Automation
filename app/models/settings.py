from sqlalchemy import Column, Integer, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func, false
from app.db.base import Base


class AppSettings(Base):
    """Per-organization settings - exactly one row per organization
    (organization_id is unique), get-or-created by SettingsService.

    Small, typed, slow-changing field set. Two fields are real FKs to
    email_templates.id, which a KV/JSONB design would lose; both must
    reference a template of the same organization.
    """

    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, unique=True, index=True)

    min_candidates_to_screen = Column(Integer, nullable=True)  # NULL = use env default
    max_candidates_to_screen = Column(Integer, nullable=True)  # NULL = use env default
    semantic_gap_threshold = Column(Float, nullable=True)      # NULL = use env default

    auto_email_on_shortlist = Column(Boolean, nullable=False, default=False, server_default=false())
    shortlist_email_template_id = Column(
        Integer, ForeignKey("email_templates.id", ondelete="SET NULL"), nullable=True
    )

    # Closes the shortlist -> interview link -> email chain: without this,
    # auto_email_on_interview_scheduled below only ever fires once a human
    # manually clicks "Create Interview Link" in Interview Workspace. When
    # true, on_decision_shortlisted also mints the interview link itself
    # (see app/services/outreach.py), which in turn triggers that email.
    auto_generate_interview_on_shortlist = Column(
        Boolean, nullable=False, default=False, server_default=false()
    )

    auto_email_on_interview_scheduled = Column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    interview_scheduled_email_template_id = Column(
        Integer, ForeignKey("email_templates.id", ondelete="SET NULL"), nullable=True
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
