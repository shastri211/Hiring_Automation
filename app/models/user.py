from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Index, text
from sqlalchemy.sql import func, true, false
from app.db.base import Base

USER_ROLES = ("admin", "member")


class User(Base):
    """An HR account. Multi-user, email+password auth (see app/services/auth.py
    and app/api/auth.py) - this app was originally single-tenant/no-auth; this
    table backs the reversal of that decision now that more than one HR
    person uses it."""

    __tablename__ = "users"
    __table_args__ = (
        # Second guard behind the plain unique `email` index: emails are
        # stored normalized (auth.normalize_user_email), and this makes a
        # case-variant duplicate impossible even if some path ever skipped
        # normalization. One email = one account, globally.
        Index("uq_users_email_lower", text("lower(email)"), unique=True),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    name = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, server_default=true())

    # "admin" | "member" within the organization.
    role = Column(String(20), nullable=False, default="member", server_default="member")
    # NULL = signed up but hasn't clicked the verification link yet.
    email_verified_at = Column(DateTime(timezone=True), nullable=True)
    # Set for admin-created accounts (admin chose a temporary password);
    # every route except /auth/me, /auth/change-password and /auth/logout
    # is refused until it's changed - see app/api/deps.py.
    must_change_password = Column(Boolean, nullable=False, default=False, server_default=false())
    # Platform operator (shared provider configuration/keys - see
    # app/api/integrations_status.py). Only grantable from the CLI
    # (scripts/create_user.py --platform-admin), never by any API.
    is_platform_admin = Column(Boolean, nullable=False, default=False, server_default=false())

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
