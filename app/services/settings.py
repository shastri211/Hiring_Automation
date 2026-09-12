import logging
from typing import Tuple

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.settings import AppSettings
from app.models.email import EmailTemplate
from app.core.config import settings

logger = logging.getLogger(__name__)


class SettingsService:
    async def get_settings(self, db: AsyncSession) -> AppSettings:
        """Get-or-create the id=1 singleton row."""
        result = await db.execute(select(AppSettings).where(AppSettings.id == 1))
        app_settings = result.scalar_one_or_none()
        if app_settings is not None:
            return app_settings

        app_settings = AppSettings(id=1)
        db.add(app_settings)
        try:
            await db.commit()
        except IntegrityError:
            # Race: another request created it first.
            await db.rollback()
            result = await db.execute(select(AppSettings).where(AppSettings.id == 1))
            app_settings = result.scalar_one_or_none()
            if app_settings is not None:
                return app_settings
            raise
        await db.refresh(app_settings)
        return app_settings

    async def update_settings(self, db: AsyncSession, patch: dict) -> AppSettings:
        app_settings = await self.get_settings(db)

        for field in ("shortlist_email_template_id", "interview_scheduled_email_template_id"):
            if field in patch and patch[field] is not None:
                template_result = await db.execute(
                    select(EmailTemplate).where(EmailTemplate.id == patch[field])
                )
                if template_result.scalar_one_or_none() is None:
                    raise ValueError(f"Email template {patch[field]} does not exist")

        for key, value in patch.items():
            setattr(app_settings, key, value)

        await db.commit()
        await db.refresh(app_settings)
        return app_settings

    async def get_effective_screening_config(self, db: AsyncSession) -> Tuple[int, int, float]:
        """Read-only lookup of the three adaptive-gate thresholds.

        Never creates a row (this runs in the screen_job hot path) - each field
        falls back individually to the env-configured default when the DB
        column (or the row itself) is NULL/missing.
        """
        result = await db.execute(select(AppSettings).where(AppSettings.id == 1))
        app_settings = result.scalar_one_or_none()

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
