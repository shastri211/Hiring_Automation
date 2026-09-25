import logging
from typing import List, Optional

from app.db.session import AsyncSessionLocal
from app.models.settings import AppSettings
from app.services import tenancy
from app.services.email import email_service
from app.services.queue import queue_service
from app.services.settings import settings_service

logger = logging.getLogger(__name__)


async def _job_org_settings(session, job_id: int) -> Optional[AppSettings]:
    """Settings of the organization that owns this job - never another
    organization's toggles/templates/test overrides."""
    organization_id = await tenancy.organization_id_for_job(session, job_id)
    if organization_id is None:
        return None
    return await settings_service.get_row(session, organization_id)


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
                app_settings = await _job_org_settings(session, job_id)
                if not app_settings:
                    return

                # Closes the shortlist -> link -> email chain: trigger_interview
                # itself calls on_interview_triggered below once it commits, so
                # if auto_email_on_interview_scheduled is also configured this
                # is what actually sends the "here's your interview link"
                # email - this toggle only controls whether the link gets
                # minted automatically in the first place. Deferred import:
                # app.services.interview imports outreach_service from this
                # module, so importing it back at module scope would be
                # circular.
                if app_settings.auto_generate_interview_on_shortlist:
                    from app.services.interview import interview_adapter

                    for resume_id in resume_ids:
                        try:
                            await interview_adapter.trigger_interview(candidate_id=resume_id, job_id=job_id)
                        except Exception:
                            logger.exception(
                                "Outreach automation: auto-generating interview link failed for "
                                "job=%s resume=%s",
                                job_id,
                                resume_id,
                            )

                if not app_settings.auto_email_on_shortlist:
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
        """Called from app/services/interview.py::trigger_interview after a
        successful trigger commit (for both a manual "Create Interview Link"
        click and the auto_generate_interview_on_shortlist path above).

        NOTE: InterviewIntegrationAdapter.trigger_interview's first parameter
        is named `candidate_id` but is actually a resume_id - call as
        `await outreach_service.on_interview_triggered(job_id=job_id, resume_id=candidate_id)`.
        """
        try:
            async with AsyncSessionLocal() as session:
                app_settings = await _job_org_settings(session, job_id)
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
