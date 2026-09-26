import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from sqlalchemy import select, or_
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
_JSON_STRING_KEYS = ("gathered_context", "cost_info", "nodes_visited")


def _normalize_evaluation_data(evaluation_data: Dict[str, Any]) -> Dict[str, Any]:
    """Best-effort json.loads of known keys Dograh may deliver as JSON strings,
    then flatten onto one canonical shape.

    Two different callers write Interview.evaluation with two different
    shapes: the live webhook (this workflow's "Notify resume-screener" node)
    sends a flat dict - {years_relevant_experience, key_skills_mentioned,
    call_duration_seconds, ...} - while the manual resync safety net
    (resync_interview in app/api/jobs.py, used when a webhook delivery is
    missed) passes Dograh's raw run detail through, nesting the same
    extraction fields plus Dograh's own call metadata under
    gathered_context/cost_info, with a "source" marker. Flattening both onto
    the same shape here means every consumer of Interview.evaluation - the
    frontend included - only ever has to handle one shape, regardless of
    which path actually wrote it.

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

    gathered_context = normalized.pop("gathered_context", None)
    if isinstance(gathered_context, dict):
        normalized.update(gathered_context)

    cost_info = normalized.pop("cost_info", None)
    if isinstance(cost_info, dict):
        normalized.update(cost_info)

    normalized.pop("source", None)
    return normalized


# Deterministic web-widget outcome classification. Every value here is a
# real, confirmed Dograh call_disposition for our WebRTC-only workflow
# (verified against the actually-deployed pipecat EndTaskReason enum and
# real historical workflow_runs, not inferred from naming conventions) - no
# LLM call anywhere in this classification.
_SYSTEM_FAILURE_DISPOSITIONS = {"pipeline_error", "unexpected_error"}
_INTERVIEW_STAGE_EXTRACTION_FIELDS = (
    "years_relevant_experience", "key_skills_mentioned", "notice_period",
    "salary_expectation", "motivation_summary", "concerns_or_gaps",
)
_MAIN_AGENDA_NODE_NAME = "Main Agenda and Questions"

# trigger_interview state groups.
_ACTIVE_STATUSES = ("SCHEDULED", "IN_PROGRESS")
_RETRIABLE_STATUSES = ("RESCHEDULE_PENDING", "FAILED")
_TERMINAL_STATUSES = ("DECLINED", "COMPLETED", "NO_SHOW")
# Every status an Interview can hold - what the status webhook may set.
INTERVIEW_STATUSES = ("PENDING",) + _ACTIVE_STATUSES + _RETRIABLE_STATUSES + _TERMINAL_STATUSES
# How long past link expiry an IN_PROGRESS interview may still wait for its
# result webhook before the sweep gives up on it (a call started just before
# expiry can legitimately finish, and report, after it).
_IN_PROGRESS_RESULT_GRACE = timedelta(hours=1)


class InterviewNotRetriableError(Exception):
    """Raised by trigger_interview when an interview cannot be (re)triggered -
    an attempt is already active, the interview is in a terminal state, or
    the retry cap has been reached. The message distinguishes which."""


def _reached_interview_stage(normalized: Dict[str, Any]) -> bool:
    """Whether the real interview questions (not just the opening greeting)
    actually ran.

    The workflow's only "End Call" node is reachable both from the opening
    stage (wrong number / candidate doesn't want to continue) and from the
    end of the real interview questions, so call_disposition == "end_call"
    alone can't tell them apart - confirmed by replaying real historical
    runs' node-transition logs, all of which never left the opening node.

    Prefers Dograh's own nodes_visited list (authoritative once the
    workflow's webhook payload_template forwards it - not yet active on the
    live webhook path, though already available on the resync path since it
    pulls gathered_context directly). Falls back to checking whether any of
    the interview-stage extraction fields got populated, since those are
    only ever set if that node's extraction actually ran. An empty
    nodes_visited list is treated as uninformative, not as proof of
    non-completion, and also falls back.
    """
    nodes_visited = normalized.get("nodes_visited")
    if isinstance(nodes_visited, list) and nodes_visited:
        return _MAIN_AGENDA_NODE_NAME in nodes_visited
    return any((normalized.get(f) or "").strip() for f in _INTERVIEW_STAGE_EXTRACTION_FIELDS)


def _classify_web_interview_outcome(call_disposition: str, normalized: Dict[str, Any]) -> str:
    """Returns "completed", "system_failure", or "inconclusive"."""
    if call_disposition == "end_call" and _reached_interview_stage(normalized):
        return "completed"
    if call_disposition in _SYSTEM_FAILURE_DISPOSITIONS:
        return "system_failure"
    return "inconclusive"


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

        Retry is an exception mechanism, not normal scheduling: raises
        InterviewNotRetriableError if an attempt is already active
        (SCHEDULED/IN_PROGRESS - retriggering here would silently invalidate
        it out from under the candidate), the interview is in a terminal
        state (DECLINED/COMPLETED/NO_SHOW), or the retry cap has been
        reached. Only RESCHEDULE_PENDING/FAILED are genuinely retriable, and
        each retry increments retry_count. provider_run_id/provider_run_attempt
        are deliberately left untouched here - they only update once the new
        attempt's own webhook arrives (see receive_evaluation).
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
                elif interview.status in _ACTIVE_STATUSES:
                    raise InterviewNotRetriableError(
                        f"Interview for job={job_id} resume={candidate_id} already has an "
                        f"active attempt (status={interview.status})."
                    )
                elif interview.status in _TERMINAL_STATUSES:
                    raise InterviewNotRetriableError(
                        f"Interview for job={job_id} resume={candidate_id} is closed "
                        f"(status={interview.status}); no further attempts."
                    )
                elif interview.status in _RETRIABLE_STATUSES:
                    if interview.retry_count >= settings.INTERVIEW_MAX_RETRY_ATTEMPTS:
                        raise InterviewNotRetriableError(
                            f"Interview for job={job_id} resume={candidate_id} has reached "
                            f"its retry limit ({settings.INTERVIEW_MAX_RETRY_ATTEMPTS})."
                        )
                    interview.retry_count += 1
                # else: PENDING - treat like a first-ever trigger.

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
                if interview.status == "DECLINED":
                    # A recruiter's decline is final - never reopened by a
                    # provider callback. Acknowledged so it isn't redelivered.
                    logger.warning(
                        "Ignoring status webhook %r for declined interview %s", status, interview.id
                    )
                    return True
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
        no duplicate side effects, completed_at set only once.

        provider_run_id/provider_run_attempt together form an attempt-
        generation fence: workflow_run_id alone can't detect "a retry has
        since superseded this run", since trigger_interview makes no
        outbound Dograh call and so never learns the new attempt's run id
        until that attempt's own first webhook arrives - see the plan for
        the full reasoning. A webhook only mutates the row if it belongs to
        the current generation; anything older (by run id, or by generation
        once a retry has happened even with an equal run id) is a safe,
        side-effect-free no-op.

        Locks the row (with_for_update) before deciding, matching the
        existing candidate_identity.py merge pattern - two concurrent
        deliveries for the same interview must not both read the same
        pre-mutation snapshot and race on which one's write wins.
        """
        async with AsyncSessionLocal() as session:
            existing = await session.execute(
                select(Interview)
                .where(
                    Interview.resume_id == candidate_id,
                    Interview.job_id == job_id
                )
                .with_for_update()
            )
            interview = existing.scalar_one_or_none()
            if not interview:
                return False

            normalized = _normalize_evaluation_data(evaluation_data)

            incoming_run_id = normalized.get("workflow_run_id")
            current_run_id = interview.provider_run_id
            is_stale = (
                incoming_run_id is not None
                and current_run_id is not None
                and (
                    int(incoming_run_id) < int(current_run_id)
                    or (
                        int(incoming_run_id) == int(current_run_id)
                        and interview.retry_count != interview.provider_run_attempt
                    )
                )
            )
            if is_stale:
                logger.warning(
                    "Ignoring stale webhook for interview %s (run %s, retry_count %s != recorded attempt %s)",
                    interview.id, incoming_run_id, interview.retry_count, interview.provider_run_attempt,
                )
                return True  # idempotent no-op - mutates nothing

            interview.evaluation = {**(interview.evaluation or {}), **normalized}

            transcript_url = normalized.get("transcript_url")
            if transcript_url:
                interview.transcript_url = transcript_url

            recording_url = normalized.get("recording_url")
            if recording_url:
                interview.recording_url = recording_url

            if incoming_run_id is not None:
                interview.provider_run_id = str(incoming_run_id)
                interview.provider_run_attempt = interview.retry_count

            if interview.status == "DECLINED":
                # A call already under way when the recruiter declined can
                # still report in. Keep its data, but the decline is final:
                # status and outcome stay as the recruiter set them.
                logger.warning("Recorded evaluation for declined interview %s without reopening it", interview.id)
                await session.commit()
                return True

            call_disposition = normalized.get("call_disposition") or ""
            interview.outcome = call_disposition or None

            outcome_kind = _classify_web_interview_outcome(call_disposition, normalized)
            if outcome_kind == "completed":
                if interview.completed_at is None:
                    interview.completed_at = datetime.now(timezone.utc)
                interview.status = "COMPLETED"
            elif outcome_kind == "system_failure":
                if interview.status != "COMPLETED":
                    interview.status = "RESCHEDULE_PENDING"
            else:
                if interview.status != "COMPLETED":
                    interview.status = "FAILED"

            await session.commit()
            return True

    async def mark_expired_interviews_as_no_show(self) -> None:
        """Periodic sweep: flips SCHEDULED interviews whose link expired with
        no run recorded for the *current* attempt generation to NO_SHOW.

        provider_run_id alone isn't enough - after a retry it still points at
        the previous (superseded) attempt until the new one's own webhook
        arrives, so an abandoned retry needs the same
        provider_run_attempt-vs-retry_count check receive_evaluation uses.
        NO_SHOW is terminal here - never auto-retried (see trigger_interview).
        """
        now = datetime.now(timezone.utc)
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Interview.id).where(
                    Interview.status == "SCHEDULED",
                    Interview.link_expires_at <= now,
                    or_(
                        Interview.provider_run_id.is_(None),
                        Interview.provider_run_attempt.is_distinct_from(Interview.retry_count),
                    ),
                )
            )
            interview_ids = [row[0] for row in result.all()]

        for interview_id in interview_ids:
            try:
                async with AsyncSessionLocal() as session:
                    interview = await session.get(Interview, interview_id)
                    # Re-check at commit time - the interview may have moved
                    # on (candidate opened the link) since the query above.
                    if interview and interview.status == "SCHEDULED":
                        interview.status = "NO_SHOW"
                        await session.commit()
            except Exception:
                logger.exception("Failed to mark interview %s as NO_SHOW", interview_id)

    async def fail_abandoned_in_progress_interviews(self) -> None:
        """Periodic sweep: an IN_PROGRESS interview (the candidate opened
        the room) whose link expired more than _IN_PROGRESS_RESULT_GRACE ago
        with no result recorded for the current attempt is marked FAILED, so
        it doesn't stay "in progress" forever and the recruiter can retry it
        (subject to the retry cap). A late result webhook still applies
        normally afterwards.
        """
        cutoff = datetime.now(timezone.utc) - _IN_PROGRESS_RESULT_GRACE
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Interview.id).where(
                    Interview.status == "IN_PROGRESS",
                    Interview.link_expires_at <= cutoff,
                    or_(
                        Interview.provider_run_id.is_(None),
                        Interview.provider_run_attempt.is_distinct_from(Interview.retry_count),
                    ),
                )
            )
            interview_ids = [row[0] for row in result.all()]

        for interview_id in interview_ids:
            try:
                async with AsyncSessionLocal() as session:
                    interview = await session.get(Interview, interview_id)
                    if interview and interview.status == "IN_PROGRESS":
                        interview.status = "FAILED"
                        interview.outcome = "no_result_received"
                        await session.commit()
            except Exception:
                logger.exception("Failed to mark abandoned interview %s as FAILED", interview_id)

interview_adapter = InterviewIntegrationAdapter()
