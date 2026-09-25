import smtplib
import asyncio
import html
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy import select, update
from app.db.session import AsyncSessionLocal
from app.models.email import EmailTemplate, EmailMessage
from app.models.profile import CandidateProfile
from app.models.job import Job
from app.models.resume import Resume
from app.models.interview import Interview
from app.services import tenancy
from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailProviderAdapter:
    """Adapter for sending emails via standard SMTP.

    Works with any SMTP server (a free Gmail/Outlook account, a self-hosted
    relay, a local dev catcher, etc.) using only Python's built-in smtplib -
    no vendor SDK, account, or paid API required. With SMTP_HOST unset (the
    default), sends are simulated - logged, not actually transmitted - so the
    app works fully out of the box with zero configuration.
    """

    def __init__(self):
        self.host = settings.SMTP_HOST
        self.port = settings.SMTP_PORT
        self.username = settings.SMTP_USERNAME
        self.password = settings.SMTP_PASSWORD
        self.use_tls = settings.SMTP_USE_TLS
        self.from_email = settings.SMTP_FROM_EMAIL

    async def send_email(self, to_email: str, subject: str, html_body: str) -> dict:
        """Sends an email and returns a provider-style response.

        `html_body` is actually plain text (templates are authored/stored as
        plain text with real newlines - see EmailTemplates.tsx's textarea and
        EmailService.render_template, both of which the UI renders correctly
        via `whitespace-pre-wrap`). It was previously handed to MIMEText as
        literal HTML with no <br>/<p> tags, so mail clients collapsed every
        newline into a single space - a structured template arrived as one
        run-on line. Escaping it and converting newlines to <br> here (SMTP
        send is the only place plain text becomes an actual HTML payload)
        fixes that without touching how templates are authored or displayed.
        """
        if not self.host:
            logger.warning(f"SMTP_HOST not configured. Simulating email to {to_email}")
            # Simulate a successful response for development if no SMTP server is set
            return {"id": f"simulated_msg_{int(datetime.utcnow().timestamp())}", "status": "simulated"}

        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = self.from_email
        message["To"] = to_email
        html_content = html.escape(html_body).replace("\n", "<br>\n")
        message.attach(MIMEText(html_content, "html"))

        try:
            await asyncio.to_thread(self._send_sync, to_email, message)
            return {"id": f"smtp_{int(datetime.utcnow().timestamp())}", "status": "sent"}
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error sending to {to_email}: {str(e)}")
            raise Exception(f"Provider Error: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            raise Exception(f"Failed to send email: {str(e)}")

    def _send_sync(self, to_email: str, message: MIMEMultipart) -> None:
        """Blocking SMTP send, run off the event loop via asyncio.to_thread."""
        with smtplib.SMTP(self.host, self.port, timeout=10) as client:
            if self.use_tls:
                client.starttls()
            if self.username and self.password:
                client.login(self.username, self.password)
            client.sendmail(self.from_email, [to_email], message.as_string())

class EmailService:
    def __init__(self):
        self.provider = EmailProviderAdapter()
        
    def render_template(self, content: str, context: dict) -> str:
        """Simple string replacement for templates."""
        rendered = content
        for key, value in context.items():
            rendered = rendered.replace(f"{{{{{key}}}}}", str(value))
        return rendered
        
    async def queue_bulk_emails(
        self,
        job_id: int,
        resume_ids: List[int],
        template_id: int,
        queue_service,
        organization_id: Optional[int] = None,
    ) -> int:
        """Creates EmailMessage records and pushes tasks to Redis for sending.

        `organization_id`: pass this when the caller already resolved and
        validated the job's organization (e.g. the bulk-send route, via
        tenancy.get_job_for_org_or_404) to skip re-deriving it here. Callers
        that haven't (outreach.py's automated sends, which only have a
        job_id) leave it None and it's looked up as before - this is still
        the service-level guarantee against a foreign template regardless of
        which caller invokes it.
        """
        queued_count = 0

        async with AsyncSessionLocal() as session:
            # 1. Fetch template - only from the job's own organization.
            job_org_id = organization_id
            if job_org_id is None:
                job_org_id = await tenancy.organization_id_for_job(session, job_id)
            result = await session.execute(
                select(EmailTemplate).where(
                    EmailTemplate.id == template_id,
                    EmailTemplate.organization_id == job_org_id,
                )
            )
            template = result.scalar_one_or_none()
            if not template:
                raise ValueError(f"Template {template_id} not found")

            # Only this job's resumes are ever messaged under this job.
            job_resume_ids = set(
                (await session.execute(
                    select(Resume.id).where(Resume.job_id == job_id, Resume.id.in_(set(resume_ids)))
                )).scalars().all()
            )

            # 2. Process each candidate
            for resume_id in resume_ids:
                if resume_id not in job_resume_ids:
                    logger.warning(f"Skipping resume {resume_id}: not a resume of job {job_id}")
                    continue
                # Check if already pending or sent for this template to prevent duplicates
                existing = await session.execute(
                    select(EmailMessage).where(
                        EmailMessage.resume_id == resume_id,
                        EmailMessage.template_id == template_id
                    )
                )
                existing_msg = existing.scalar_one_or_none()
                
                # BLOCKED is historical only (the allowlist gate that ever
                # produced it is gone) - never auto-resumed. Nothing revalidated
                # that address when the allowlist existed, so silently treating
                # it like a retryable FAILED would send, for real, to an
                # address a human never actually approved. It stays frozen
                # until someone reviews it and re-sends deliberately (e.g. by
                # clearing status via direct DB access).
                if existing_msg and existing_msg.status in ["PENDING", "SENT", "BLOCKED"]:
                    logger.info(f"Skipping resume {resume_id}: Email already {existing_msg.status}")
                    continue
                
                # Fetch candidate context
                candidate_result = await session.execute(
                    select(CandidateProfile).where(CandidateProfile.resume_id == resume_id)
                )
                candidate = candidate_result.scalar_one_or_none()
                
                job_result = await session.execute(
                    select(Job).where(Job.id == job_id)
                )
                job = job_result.scalar_one_or_none()
                
                if not candidate or not candidate.email:
                    logger.warning(f"Skipping resume {resume_id}: No email address available")
                    # Could create a FAILED record here, but skipping is safer to avoid noise
                    continue
                    
                if not job:
                    continue

                # A real interview link only exists once trigger_interview has
                # minted a public_token for this (job_id, resume_id). If the
                # template needs {{interview_link}} but no active, non-expired
                # link exists yet, skip only this candidate (log + continue) -
                # matching the existing "no email on file -> skip" pattern -
                # rather than blocking the whole batch, and rather than ever
                # emailing a dead/expired link.
                interview_link = None
                needs_interview_link = (
                    "{{interview_link}}" in template.body_content
                    or "{{interview_link}}" in template.subject
                )
                if needs_interview_link:
                    interview_res = await session.execute(
                        select(Interview).where(
                            Interview.job_id == job_id,
                            Interview.resume_id == resume_id,
                        )
                    )
                    interview = interview_res.scalar_one_or_none()
                    now = datetime.now(timezone.utc)
                    link_expires_at = interview.link_expires_at if interview else None
                    if link_expires_at is not None and link_expires_at.tzinfo is None:
                        link_expires_at = link_expires_at.replace(tzinfo=timezone.utc)
                    link_is_live = (
                        interview is not None
                        and interview.public_token
                        and settings.PUBLIC_APP_BASE_URL
                        and (link_expires_at is None or link_expires_at > now)
                    )
                    if link_is_live:
                        interview_link = f"{settings.PUBLIC_APP_BASE_URL}/interview-room/{interview.public_token}"
                    else:
                        logger.warning(
                            f"Skipping resume {resume_id}: template requires {{{{interview_link}}}} but no "
                            "active, non-expired interview link exists yet."
                        )
                        continue

                context = {
                    "candidate_name": (candidate.name if candidate else None) or "Candidate",
                    "job_title": job.title,
                    "interview_link": interview_link or "",
                }
                
                # Render content
                subject = self.render_template(template.subject, context)
                body = self.render_template(template.body_content, context)
                
                # Create message record. FAILED is the only resumable prior
                # attempt for this (resume_id, template_id) pair - BLOCKED is
                # filtered out above and never reaches here. The unique
                # constraint means a fresh insert for FAILED would raise
                # IntegrityError, so it must update the existing row in place.
                if existing_msg and existing_msg.status == "FAILED":
                    # Retry flow: update existing
                    existing_msg.status = "PENDING"
                    existing_msg.subject = subject
                    existing_msg.body_content = body
                    existing_msg.error_message = None
                    msg_id = existing_msg.id
                else:
                    # New flow
                    new_msg = EmailMessage(
                        job_id=job_id,
                        resume_id=resume_id,
                        template_id=template_id,
                        subject=subject,
                        body_content=body,
                        status="PENDING",
                    )
                    session.add(new_msg)
                    await session.flush() # flush to get ID
                    msg_id = new_msg.id
                
                await session.commit()

                # Push to the shared worker queue (same stream/contract as every
                # other producer; app/worker.py already has a SEND_EMAIL handler).
                await queue_service.enqueue_task({
                    "action": "SEND_EMAIL",
                    "email_message_id": msg_id
                })
                queued_count += 1
                
        return queued_count

    async def process_send_email_task(self, email_message_id: int):
        """Worker function to actually send the email via the provider."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(EmailMessage).where(EmailMessage.id == email_message_id)
            )
            msg = result.scalar_one_or_none()
            
            if not msg:
                logger.error(f"EmailMessage {email_message_id} not found")
                return
                
            if msg.status != "PENDING":
                logger.info(f"EmailMessage {email_message_id} already processed ({msg.status})")
                return

            if msg.send_attempt_started_at is not None:
                # A previous attempt reached the provider call and never
                # came back to record SENT/FAILED - most likely a crash
                # right after a successful send but before that commit.
                # Whether it actually delivered can't be determined from
                # here, so this fails safe: never silently retry a send
                # that might already have reached the candidate. Surfaced
                # as FAILED (not silently skipped) so it's visible in
                # Outreach History and can be manually verified/resent.
                msg.status = "FAILED"
                msg.error_message = (
                    "A previous send attempt for this message did not complete cleanly "
                    "(process likely crashed mid-send) - it may or may not have reached the "
                    "candidate. Verify manually before resending."
                )
                await session.commit()
                logger.error(
                    f"EmailMessage {email_message_id}: prior send attempt at "
                    f"{msg.send_attempt_started_at} never completed - marking FAILED instead of "
                    "risking a duplicate send."
                )
                return

            msg.send_attempt_started_at = datetime.utcnow()
            await session.commit()


            # Recipient is always the candidate's own email as extracted
            # from their resume (CandidateProfile.email) - there is no
            # explicit-override or test-allowlist redirect/gate here.
            profile_result = await session.execute(
                select(CandidateProfile).where(CandidateProfile.resume_id == msg.resume_id)
            )
            profile = profile_result.scalar_one_or_none()

            if not profile or not profile.email:
                msg.status = "FAILED"
                msg.error_message = "Candidate profile not found or has no email address."
                await session.commit()
                return
            recipient_email = profile.email

            try:
                # Call Provider
                provider_response = await self.provider.send_email(
                    to_email=recipient_email,
                    subject=msg.subject,
                    html_body=msg.body_content
                )

                # Update success
                msg.status = "SENT"
                msg.provider_message_id = provider_response.get("id")
                msg.sent_at = datetime.utcnow()
                await session.commit()
                logger.info(f"Successfully sent email message {email_message_id} to {recipient_email}")
                
            except Exception as e:
                # Update failure
                msg.status = "FAILED"
                msg.error_message = str(e)
                await session.commit()
                logger.error(f"Failed to send email message {email_message_id}: {str(e)}")
                raise # Re-raise for worker retry logic if configured

email_service = EmailService()
