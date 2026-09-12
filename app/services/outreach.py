import logging
from typing import List

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.settings import AppSettings
from app.services.email import email_service
from app.services.queue import queue_service

logger = logging.getLogger(__name__)


class OutreachAutomationService:
    """Event-triggered outreach automation.

    Reads AppSettings toggles and, if enabled, delegates to the existing
    email_service.queue_bulk_emails (no duplicated send logic - dedupe is
    already handled there via the (resume_id, template_id) unique constraint).

    Opens its own DB session (mirrors email_service.queue_bulk_emails) rather
    than reusing a caller-supplied session, and every public method's entire
    body is wrapped so a failure here (bad template, no email on file, DB
    hiccup) never propagates to / fails the request it's attached to.
    """

    async def on_decision_shortlisted(self, job_id: int, resume_ids: List[int]) -> None:
        if not resume_ids:
            return
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(AppSettings).where(AppSettings.id == 1))
                app_settings = result.scalar_one_or_none()
                if not app_settings or not app_settings.auto_email_on_shortlist:
                    return
                if not app_settings.shortlist_email_template_id:
                    logger.warning(
                        "auto_email_on_shortlist is enabled but no shortlist_email_template_id "
                        "is configured; skipping outreach for job=%s",
                        job_id,
                    )
                    return

                await email_service.queue_bulk_emails(
                    job_id=job_id,
                    resume_ids=resume_ids,
                    template_id=app_settings.shortlist_email_template_id,
                    queue_service=queue_service,
                )
        except Exception:
            logger.exception(
                "Outreach automation (on_decision_shortlisted) failed for job=%s resume_ids=%s",
                job_id,
                resume_ids,
            )

    async def on_interview_triggered(self, job_id: int, resume_id: int) -> None:
        """Call this from app/services/interview.py::trigger_interview after a
        successful trigger commit. Not wired in by this change - built here so
        the Dograh work stream can call it without needing to touch this file.

        NOTE: InterviewIntegrationAdapter.trigger_interview's first parameter
        is named `candidate_id` but is actually a resume_id - call as
        `await outreach_service.on_interview_triggered(job_id=job_id, resume_id=candidate_id)`.
        """
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(AppSettings).where(AppSettings.id == 1))
                app_settings = result.scalar_one_or_none()
                if not app_settings or not app_settings.auto_email_on_interview_scheduled:
                    return
                if not app_settings.interview_scheduled_email_template_id:
                    logger.warning(
                        "auto_email_on_interview_scheduled is enabled but no "
                        "interview_scheduled_email_template_id is configured; skipping outreach "
                        "for job=%s resume=%s",
                        job_id,
                        resume_id,
                    )
                    return

                await email_service.queue_bulk_emails(
                    job_id=job_id,
                    resume_ids=[resume_id],
                    template_id=app_settings.interview_scheduled_email_template_id,
                    queue_service=queue_service,
                )
        except Exception:
            logger.exception(
                "Outreach automation (on_interview_triggered) failed for job=%s resume=%s",
                job_id,
                resume_id,
            )


outreach_service = OutreachAutomationService()
