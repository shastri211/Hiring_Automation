import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.interview import Interview
from app.services.dograh import dograh_client
from app.services.outreach import outreach_service

logger = logging.getLogger(__name__)

# Keys whose value Dograh's webhook renderer delivers as a JSON-encoded
# *string* rather than a nested object (confirmed by reading
# D:\projects\dograh\api\utils\template_renderer.py: a payload_template
# string leaf that is exactly a "{{variable}}" placeholder for a dict/list
# value is rendered via json.dumps(value) and spliced back in as a string).
# Our own tests/manual resync pass real dicts directly, which json.loads
# would reject as non-string input, so this only fires for actual strings.
_JSON_STRING_KEYS = ("gathered_context", "cost_info")


def _normalize_evaluation_data(evaluation_data: Dict[str, Any]) -> Dict[str, Any]:
    """Best-effort json.loads of known keys Dograh may deliver as JSON strings.

    Never raises - a webhook receiver must not fail on unexpected shapes.
    Leaves the original string in place if it isn't valid JSON.
    """
    normalized = dict(evaluation_data or {})
    for key in _JSON_STRING_KEYS:
        value = normalized.get(key)
        if isinstance(value, str):
            try:
                normalized[key] = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                pass
    return normalized


class InterviewIntegrationAdapter:
    async def trigger_interview(self, candidate_id: int, job_id: int) -> bool:
        """
        Triggers a Dograh browser/web interview.

        Dograh issues no candidate-facing "join URL" of its own (its browser
        widget authenticates lazily against the embed token when the
        candidate opens our page), so there is no outbound Dograh call here
        at all - we simply mint our own opaque, single-purpose interview
        link (public_token) pointing at our own frontend and mark the
        interview SCHEDULED. If Dograh isn't configured, we still succeed
        locally (log a warning) - the resulting link will just 501 if
        visited, mirroring EmailProviderAdapter's "simulate when
        unconfigured" posture.
        """
        if not dograh_client.is_configured:
            logger.warning(
                "Dograh is not fully configured (DOGRAH_BASE_URL/DOGRAH_EMBED_TOKEN/"
                "PUBLIC_APP_BASE_URL); the interview link for job=%s resume=%s will be "
                "minted but will not work until configuration is complete.",
                job_id,
                candidate_id,
            )

        now = datetime.now(timezone.utc)
        public_token = secrets.token_urlsafe(32)
        link_expires_at = now + timedelta(hours=settings.DOGRAH_INTERVIEW_LINK_TTL_HOURS)

        async with AsyncSessionLocal() as session:
            try:
                existing = await session.execute(
                    select(Interview).where(
                        Interview.resume_id == candidate_id,
                        Interview.job_id == job_id
                    )
                )
                interview = existing.scalar_one_or_none()
                if not interview:
                    interview = Interview(
                        resume_id=candidate_id,
                        job_id=job_id,
                    )
                    session.add(interview)

                # Regenerated on every (re)trigger - invalidates any prior link.
                interview.public_token = public_token
                interview.link_expires_at = link_expires_at
                interview.provider = "dograh"
                interview.status = "SCHEDULED"
                interview.scheduled_at = now

                await session.commit()
            except IntegrityError:
                await session.rollback()
                # Race condition (e.g. concurrent trigger) - the other writer
                # already produced a valid SCHEDULED interview; treat as success.
                return True

        await outreach_service.on_interview_triggered(job_id=job_id, resume_id=candidate_id)
        return True

    async def receive_interview_status(self, candidate_id: int, job_id: int, status: str) -> bool:
        async with AsyncSessionLocal() as session:
            existing = await session.execute(
                select(Interview).where(
                    Interview.resume_id == candidate_id,
                    Interview.job_id == job_id
                )
            )
            interview = existing.scalar_one_or_none()
            if interview:
                interview.status = status
                await session.commit()
                return True
            return False

    async def receive_transcript(self, candidate_id: int, job_id: int, transcript: str) -> bool:
        async with AsyncSessionLocal() as session:
            existing = await session.execute(
                select(Interview).where(
                    Interview.resume_id == candidate_id,
                    Interview.job_id == job_id
                )
            )
            interview = existing.scalar_one_or_none()
            if interview:
                interview.transcript = transcript
                await session.commit()
                return True
            return False

    async def receive_evaluation(self, candidate_id: int, job_id: int, evaluation_data: Dict[str, Any]) -> bool:
        """Merge-based, idempotent evaluation receiver.

        Dograh webhook delivery may redeliver (transient-failure retries), and
        the manual resync endpoint may also call this more than once for the
        same run, so this must be safe to call twice with the same payload:
        no duplicate side effects, completed_at set only once, provider_run_id
        only set if not already recorded.
        """
        async with AsyncSessionLocal() as session:
            existing = await session.execute(
                select(Interview).where(
                    Interview.resume_id == candidate_id,
                    Interview.job_id == job_id
                )
            )
            interview = existing.scalar_one_or_none()
            if not interview:
                return False

            normalized = _normalize_evaluation_data(evaluation_data)

            interview.evaluation = {**(interview.evaluation or {}), **normalized}

            transcript_url = normalized.get("transcript_url")
            if transcript_url:
                interview.transcript_url = transcript_url

            recording_url = normalized.get("recording_url")
            if recording_url:
                interview.recording_url = recording_url

            run_id = normalized.get("workflow_run_id")
            if run_id and not interview.provider_run_id:
                interview.provider_run_id = str(run_id)

            if interview.completed_at is None:
                interview.completed_at = datetime.now(timezone.utc)

            interview.status = "COMPLETED"
            await session.commit()
            return True

interview_adapter = InterviewIntegrationAdapter()
