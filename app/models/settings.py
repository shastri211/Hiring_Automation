from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.sql import func, false
from app.db.base import Base


class AppSettings(Base):
    """Single-row (id=1) singleton settings table.

    Single-tenant, small, typed, slow-changing field set. Two fields are real
    FKs to email_templates.id, which a KV/JSONB design would lose.
    """

    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True)

    org_name = Column(String(255), nullable=True)

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

    # Comma-separated recipient allowlist for outbound candidate email while
    # testing with non-real candidate data. When set (non-empty), any send
    # whose recipient isn't in this list is blocked before it reaches the email provider.
    # NULL/empty means "no addresses cleared yet" -> every send is blocked,
    # which is the safer default until the user opts specific addresses in.
    email_test_allowlist = Column(Text, nullable=True)

    # Persistent, global counterpart to a manual bulk-send's per-click test
    # recipient override (app.schemas.email.BulkEmailRequest.
    # override_recipient_email): when set, EVERY email - including fully
    # automated shortlist/interview-scheduled sends, which have no per-send
    # moment to type an override into - is redirected here instead of the
    # real candidate address, bypassing email_test_allowlist. Clear it
    # before going to production.
    email_test_override_recipient = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
