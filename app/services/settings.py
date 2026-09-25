import logging
from typing import Optional, Tuple

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.settings import AppSettings
from app.models.email import EmailTemplate
from app.core.config import settings

logger = logging.getLogger(__name__)


class SettingsService:
    """Per-organization settings: exactly one AppSettings row per
    organization (organization_id is unique). Every caller passes the
    organization explicitly - a request's comes from the logged-in user, a
    background task's from the job it is acting on."""

    async def get_row(self, db: AsyncSession, organization_id: int) -> Optional[AppSettings]:
        """Read-only lookup - never creates a row (safe in worker hot paths)."""
        result = await db.execute(select(AppSettings).where(AppSettings.organization_id == organization_id))
        return result.scalar_one_or_none()

    def new_settings_row(self, organization_id: int) -> AppSettings:
        """A freshly-constructed row for `organization_id`, not yet added to
        any session - the single place that defines what a brand-new
        organization's settings look like. Used by get_settings's
        create-branch below, and by signup (app/api/auth.py), which needs
        the row created in the same atomic commit as the Organization/User
        rows rather than get_settings's own separate commit."""
        return AppSettings(organization_id=organization_id)

    async def get_settings(self, db: AsyncSession, organization_id: int) -> AppSettings:
        """Get-or-create the organization's row."""
        app_settings = await self.get_row(db, organization_id)
        if app_settings is not None:
            return app_settings

        app_settings = self.new_settings_row(organization_id)
        db.add(app_settings)
        try:
            await db.commit()
        except IntegrityError:
            # Race: another request created this organization's row first
            # (unique organization_id).
            await db.rollback()
            app_settings = await self.get_row(db, organization_id)
            if app_settings is not None:
                return app_settings
            raise
        await db.refresh(app_settings)
        return app_settings

    async def update_settings(self, db: AsyncSession, organization_id: int, patch: dict) -> AppSettings:
        app_settings = await self.get_settings(db, organization_id)

        for field in ("shortlist_email_template_id", "interview_scheduled_email_template_id"):
            if field in patch and patch[field] is not None:
                # Same "does not exist" error whether the template is missing
                # or belongs to another organization.
                template_result = await db.execute(
                    select(EmailTemplate).where(
                        EmailTemplate.id == patch[field],
                        EmailTemplate.organization_id == organization_id,
                    )
                )
                if template_result.scalar_one_or_none() is None:
                    raise ValueError(f"Email template {patch[field]} does not exist")

        for key, value in patch.items():
            setattr(app_settings, key, value)

        await db.commit()
        await db.refresh(app_settings)
        return app_settings

    async def get_effective_screening_config(self, db: AsyncSession, organization_id: int) -> Tuple[int, int, float]:
        """Read-only lookup of the three adaptive-gate thresholds.

        Never creates a row (this runs in the screen_job hot path) - each field
        falls back individually to the env-configured default when the DB
        column (or the row itself) is NULL/missing.
        """
        app_settings = await self.get_row(db, organization_id)

        min_keep = settings.MIN_CANDIDATES_TO_SCREEN
        max_keep = settings.MAX_CANDIDATES_TO_SCREEN
        gap_threshold = settings.SEMANTIC_GAP_THRESHOLD

        if app_settings is not None:
            if app_settings.min_candidates_to_screen is not None:
                min_keep = app_settings.min_candidates_to_screen
            if app_settings.max_candidates_to_screen is not None:
                max_keep = app_settings.max_candidates_to_screen
            if app_settings.semantic_gap_threshold is not None:
                gap_threshold = app_settings.semantic_gap_threshold

        return min_keep, max_keep, gap_threshold


settings_service = SettingsService()
