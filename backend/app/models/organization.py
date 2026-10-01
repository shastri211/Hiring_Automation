from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from app.db.base import Base


class Organization(Base):
    """A company/tenant. Every root table (jobs, candidates, users,
    email_templates, app_settings, talent_pool_entries) carries an
    organization_id; everything else is scoped through those roots (e.g.
    resumes/screening results/interviews through their job).

    Also the lock target for membership changes: user role/active changes
    take SELECT ... FOR UPDATE on this row so the last-active-admin check
    can't race (see app/api/auth.py).
    """

    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
