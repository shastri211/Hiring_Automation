import httpx
import logging
from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy import select, update
from app.db.session import AsyncSessionLocal
from app.models.email import EmailTemplate, EmailMessage
from app.models.profile import CandidateProfile
from app.models.job import Job
from app.models.interview import Interview
from app.models.settings import AppSettings
from app.core.config import settings

logger = logging.getLogger(__name__)


def _parse_allowlist(raw: Optional[str]) -> set[str]:
    if not raw:
        return set()
    return {addr.strip().lower() for addr in raw.split(",") if addr.strip()}

class EmailProviderAdapter:
    """Adapter for sending emails via Resend HTTP API"""
    
    def __init__(self):
        self.api_key = settings.RESEND_API_KEY
        self.from_email = settings.RESEND_FROM_EMAIL
        self.api_url = "https://api.resend.com/emails"
        
    async def send_email(self, to_email: str, subject: str, html_body: str) -> dict:
        """Sends an email and returns the provider response."""
        if not self.api_key:
            logger.warning(f"RESEND_API_KEY not configured. Simulating email to {to_email}")
            # Simulate a successful response for development if no key is set
            return {"id": f"simulated_msg_{int(datetime.utcnow().timestamp())}", "status": "simulated"}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "from": self.from_email,
            "to": [to_email],
            "subject": subject,
            "html": html_body
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.api_url, 
                    headers=headers, 
                    json=payload,
                    timeout=10.0
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                error_body = e.response.text
                logger.error(f"Resend API error: {e.response.status_code} - {error_body}")
                raise Exception(f"Provider Error: {e.response.status_code} - {error_body}")
            except Exception as e:
                logger.error(f"Failed to send email to {to_email}: {str(e)}")
                raise Exception(f"Failed to send email: {str(e)}")

class EmailService:
    def __init__(self):
        self.provider = EmailProviderAdapter()
        
    def render_template(self, content: str, context: dict) -> str:
        """Simple string replacement for templates."""
        rendered = content
        for key, value in context.items():
            rendered = rendered.replace(f"{{{{{key}}}}}", str(value))
        return rendered
        
    async def queue_bulk_emails(self, job_id: int, resume_ids: List[int], template_id: int, queue_service) -> int:
        """Creates EmailMessage records and pushes tasks to Redis for sending."""
        queued_count = 0
        
        async with AsyncSessionLocal() as session:
            # 1. Fetch template
            result = await session.execute(
                select(EmailTemplate).where(EmailTemplate.id == template_id)
            )
            template = result.scalar_one_or_none()
            if not template:
                raise ValueError(f"Template {template_id} not found")
                
            # 2. Process each candidate
            for resume_id in resume_ids:
                # Check if already pending or sent for this template to prevent duplicates
                existing = await session.execute(
                    select(EmailMessage).where(
                        EmailMessage.resume_id == resume_id,
                        EmailMessage.template_id == template_id
                    )
                )
                existing_msg = existing.scalar_one_or_none()
                
                if existing_msg and existing_msg.status in ["PENDING", "SENT"]:
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
                    "candidate_name": candidate.name or "Candidate",
                    "job_title": job.title,
                    "interview_link": interview_link or "",
                }
                
                # Render content
                subject = self.render_template(template.subject, context)
                body = self.render_template(template.body_content, context)
                
                # Create message record
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
                        status="PENDING"
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
                
            # Get recipient email
            profile_result = await session.execute(
                select(CandidateProfile).where(CandidateProfile.resume_id == msg.resume_id)
            )
            profile = profile_result.scalar_one_or_none()
            
            if not profile or not profile.email:
                msg.status = "FAILED"
                msg.error_message = "Candidate profile not found or has no email address."
                await session.commit()
                return

            # Test-data safety net: candidate emails are frequently extracted
            # from non-real sample resumes. Only addresses the user has
            # explicitly cleared in Settings > Outreach Automation are allowed
            # to actually receive mail via Resend; everything else is blocked
            # before it ever reaches the provider (recorded as BLOCKED, not FAILED,
            # so it doesn't look like an error and isn't retried).
            allowlist_row = (
                await session.execute(select(AppSettings).where(AppSettings.id == 1))
            ).scalar_one_or_none()
            allowlist = _parse_allowlist(allowlist_row.email_test_allowlist if allowlist_row else None)
            if profile.email.strip().lower() not in allowlist:
                msg.status = "BLOCKED"
                msg.error_message = (
                    f"Recipient {profile.email} is not in the test email allowlist "
                    "(Settings > Outreach Automation). Add it there to allow sending."
                )
                await session.commit()
                logger.warning(
                    f"Blocked email message {email_message_id}: {profile.email} not in test allowlist"
                )
                return

            try:
                # Call Provider
                provider_response = await self.provider.send_email(
                    to_email=profile.email,
                    subject=msg.subject,
                    html_body=msg.body_content
                )
                
                # Update success
                msg.status = "SENT"
                msg.provider_message_id = provider_response.get("id")
                msg.sent_at = datetime.utcnow()
                await session.commit()
                logger.info(f"Successfully sent email message {email_message_id} to {profile.email}")
                
            except Exception as e:
                # Update failure
                msg.status = "FAILED"
                msg.error_message = str(e)
                await session.commit()
                logger.error(f"Failed to send email message {email_message_id}: {str(e)}")
                raise # Re-raise for worker retry logic if configured

email_service = EmailService()
