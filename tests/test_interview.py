import json
from unittest.mock import patch, AsyncMock

import pytest
from sqlalchemy import select

from app.services.interview import InterviewIntegrationAdapter, InterviewNotRetriableError
from app.models.job import Job
from app.models.batch import ScreeningBatch
from app.models.resume import Resume
from app.models.interview import Interview
from tenancy_fixtures import TEST_ORG_ID


@pytest.mark.asyncio
@patch("app.services.interview.AsyncSessionLocal")
async def test_interview_adapter(mock_session_local):
    adapter = InterviewIntegrationAdapter()

    assert hasattr(adapter, "trigger_interview")
    assert hasattr(adapter, "receive_interview_status")
    assert hasattr(adapter, "receive_transcript")
    assert hasattr(adapter, "receive_evaluation")


@pytest.fixture
async def setup_job_and_resume(db_session):
    job = Job(organization_id=TEST_ORG_ID, title="Test Job", description="A test job description")
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    batch = ScreeningBatch(job_id=job.id, status="COMPLETED", total_resumes=1)
    db_session.add(batch)
    await db_session.commit()
    await db_session.refresh(batch)

    resume = Resume(
        job_id=job.id,
        batch_id=batch.id,
        filename="test_resume.pdf",
        file_hash=f"dummy_hash_{id(batch)}",
        storage_key="dummy_key",
        status="PROCESSED",
    )
    db_session.add(resume)
    await db_session.commit()
    await db_session.refresh(resume)

    return job, resume


async def _fetch_interview(db_session, job_id, resume_id):
    # The adapter commits via its own AsyncSessionLocal() session, so this
    # test session's identity map may hold a stale (pre-update) copy of the
    # same row. populate_existing=True forces the fresh DB values to
    # overwrite it, without the greenlet issues that db_session.expire_all()
    # triggers if a plain attribute (e.g. .id) is accessed afterward outside
    # an awaited context.
    result = await db_session.execute(
        select(Interview)
        .where(Interview.job_id == job_id, Interview.resume_id == resume_id)
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


# -- trigger_interview -------------------------------------------------------

@pytest.mark.asyncio
@patch("app.services.interview.outreach_service.on_interview_triggered", new_callable=AsyncMock)
async def test_trigger_interview_generates_token_and_calls_outreach(
    mock_outreach, setup_job_and_resume, db_session
):
    job, resume = setup_job_and_resume

    adapter = InterviewIntegrationAdapter()
    success = await adapter.trigger_interview(resume.id, job.id)
    assert success is True

    interview = await _fetch_interview(db_session, job.id, resume.id)
    assert interview is not None
    assert interview.public_token
    assert len(interview.public_token) > 20
    assert interview.link_expires_at is not None
    assert interview.provider == "dograh"
    assert interview.status == "SCHEDULED"
    assert interview.scheduled_at is not None

    mock_outreach.assert_awaited_once_with(job_id=job.id, resume_id=resume.id)


@pytest.mark.asyncio
@patch("app.services.interview.outreach_service.on_interview_triggered", new_callable=AsyncMock)
async def test_trigger_interview_get_or_create_reuses_same_row(
    mock_outreach, setup_job_and_resume, db_session
):
    """get-or-create must key on the same (job_id, resume_id) row rather than
    creating a duplicate - verified via the retriable-state path (RESCHEDULE_
    PENDING), since re-triggering a still-SCHEDULED row is now refused
    (see test_trigger_interview_refuses_when_already_active) rather than
    silently regenerating an active link out from under the candidate."""
    job, resume = setup_job_and_resume
    adapter = InterviewIntegrationAdapter()

    await adapter.trigger_interview(resume.id, job.id)
    first = await _fetch_interview(db_session, job.id, resume.id)
    first_token = first.public_token

    first.status = "RESCHEDULE_PENDING"
    await db_session.commit()

    await adapter.trigger_interview(resume.id, job.id)
    second = await _fetch_interview(db_session, job.id, resume.id)

    assert second.public_token != first_token
    assert second.id == first.id  # same row, get-or-create - not a duplicate
    assert second.status == "SCHEDULED"
    assert second.retry_count == 1


@pytest.mark.asyncio
@patch("app.services.interview.outreach_service.on_interview_triggered", new_callable=AsyncMock)
@patch("app.services.interview.dograh_client")
async def test_trigger_interview_succeeds_when_not_configured(
    mock_dograh_client, mock_outreach, setup_job_and_resume, db_session
):
    """No outbound Dograh call happens at trigger time regardless of
    configuration - the widget lazily creates the run when the candidate
    opens the page. trigger_interview must still succeed locally (log a
    warning) when Dograh isn't configured."""
    mock_dograh_client.is_configured = False
    job, resume = setup_job_and_resume

    adapter = InterviewIntegrationAdapter()
    success = await adapter.trigger_interview(resume.id, job.id)
    assert success is True

    interview = await _fetch_interview(db_session, job.id, resume.id)
    assert interview.public_token
    assert interview.status == "SCHEDULED"
    mock_outreach.assert_awaited_once()


@pytest.mark.asyncio
@patch("app.services.interview.outreach_service.on_interview_triggered", new_callable=AsyncMock)
@patch("app.services.interview.dograh_client")
async def test_trigger_interview_succeeds_when_configured(
    mock_dograh_client, mock_outreach, setup_job_and_resume, db_session
):
    mock_dograh_client.is_configured = True
    job, resume = setup_job_and_resume

    adapter = InterviewIntegrationAdapter()
    success = await adapter.trigger_interview(resume.id, job.id)
    assert success is True
    mock_outreach.assert_awaited_once()


# -- receive_evaluation -------------------------------------------------------

@pytest.mark.asyncio
async def test_receive_evaluation_merges_and_normalizes_json_string_fields(
    setup_job_and_resume, db_session
):
    job, resume = setup_job_and_resume
    interview = Interview(job_id=job.id, resume_id=resume.id, status="SCHEDULED")
    db_session.add(interview)
    await db_session.commit()

    adapter = InterviewIntegrationAdapter()

    # Simulates the real Dograh delivery shape: gathered_context/cost_info
    # arrive as JSON-encoded strings (confirmed against Dograh's template
    # renderer), not nested objects. "end_call" + a populated interview-stage
    # extraction field is the real, confirmed disposition/evidence pair for a
    # genuinely completed web interview.
    payload = {
        "source": "dograh",
        "workflow_run_id": 555,
        "call_disposition": "end_call",
        "years_relevant_experience": "5 years",
        "gathered_context": json.dumps({"call_disposition": "end_call", "sentiment": "positive"}),
        "cost_info": json.dumps({"call_duration_seconds": 120}),
        "transcript_url": "https://dograh.example.com/t/abc",
        "recording_url": "https://dograh.example.com/r/abc",
    }

    success = await adapter.receive_evaluation(resume.id, job.id, payload)
    assert success is True

    stored = await _fetch_interview(db_session, job.id, resume.id)
    assert stored.status == "COMPLETED"
    assert stored.transcript_url == "https://dograh.example.com/t/abc"
    assert stored.recording_url == "https://dograh.example.com/r/abc"
    assert stored.provider_run_id == "555"
    assert stored.completed_at is not None
    # JSON-string fields are normalized back into real dicts, then flattened
    # onto the canonical shape - no nested gathered_context/cost_info/source
    # left for consumers to special-case.
    assert stored.evaluation["sentiment"] == "positive"
    assert stored.evaluation["call_disposition"] == "end_call"
    assert stored.evaluation["call_duration_seconds"] == 120
    assert stored.outcome == "end_call"
    assert "gathered_context" not in stored.evaluation
    assert "cost_info" not in stored.evaluation
    assert "source" not in stored.evaluation

    first_completed_at = stored.completed_at

    # Redelivery of the exact same payload must be a safe no-op: completed_at
    # unchanged, provider_run_id unchanged, no duplicate rows.
    success_again = await adapter.receive_evaluation(resume.id, job.id, payload)
    assert success_again is True

    stored_again = await _fetch_interview(db_session, job.id, resume.id)
    assert stored_again.completed_at == first_completed_at
    assert stored_again.provider_run_id == "555"
    assert stored_again.status == "COMPLETED"


@pytest.mark.asyncio
async def test_receive_evaluation_accepts_real_dicts_directly(setup_job_and_resume, db_session):
    """Our own callers (manual resync, direct tests) pass real dicts, not
    JSON strings - normalization must flatten them onto the canonical shape
    without erroring."""
    job, resume = setup_job_and_resume
    interview = Interview(job_id=job.id, resume_id=resume.id, status="SCHEDULED")
    db_session.add(interview)
    await db_session.commit()

    adapter = InterviewIntegrationAdapter()
    payload = {
        "workflow_run_id": 42,
        "gathered_context": {"call_disposition": "completed"},
        "cost_info": {"call_duration_seconds": 30},
    }
    success = await adapter.receive_evaluation(resume.id, job.id, payload)
    assert success is True

    stored = await _fetch_interview(db_session, job.id, resume.id)
    assert stored.evaluation["call_disposition"] == "completed"
    assert stored.evaluation["call_duration_seconds"] == 30
    assert "gathered_context" not in stored.evaluation
    assert stored.provider_run_id == "42"


@pytest.mark.asyncio
async def test_receive_evaluation_missing_interview_returns_false(db_session):
    adapter = InterviewIntegrationAdapter()
    success = await adapter.receive_evaluation(999999, 999999, {"score": 1})
    assert success is False


# -- deterministic web-widget outcome classification -------------------------
# Every disposition below is a real, confirmed Dograh call_disposition for
# our WebRTC-only workflow (see the plan for the live-verification behind
# this table) - no LLM call anywhere in this classification.

@pytest.mark.asyncio
async def test_receive_evaluation_end_call_without_extraction_fields_is_failed(
    setup_job_and_resume, db_session
):
    """This is the case that would have been wrong before this feature: the
    workflow's only End Call node is reachable both from the opening stage
    (before any real interview) and from after the real questions, so
    call_disposition == "end_call" alone can't prove completion. Confirmed
    empirically against all 3 real historical "end_call" runs on our
    workflow, none of which ever reached the interview stage."""
    job, resume = setup_job_and_resume
    interview = Interview(job_id=job.id, resume_id=resume.id, status="SCHEDULED")
    db_session.add(interview)
    await db_session.commit()

    adapter = InterviewIntegrationAdapter()
    payload = {
        "workflow_run_id": 7,
        "call_disposition": "end_call",
        "years_relevant_experience": "",
        "key_skills_mentioned": "",
        "notice_period": "",
        "salary_expectation": "",
        "motivation_summary": "",
        "concerns_or_gaps": "",
    }
    success = await adapter.receive_evaluation(resume.id, job.id, payload)
    assert success is True

    stored = await _fetch_interview(db_session, job.id, resume.id)
    assert stored.status == "FAILED"
    assert stored.outcome == "end_call"
    assert stored.completed_at is None


@pytest.mark.asyncio
@pytest.mark.parametrize("call_disposition", ["pipeline_error", "unexpected_error"])
async def test_receive_evaluation_system_failure_dispositions_reschedule_pending(
    call_disposition, setup_job_and_resume, db_session
):
    job, resume = setup_job_and_resume
    interview = Interview(job_id=job.id, resume_id=resume.id, status="SCHEDULED")
    db_session.add(interview)
    await db_session.commit()

    adapter = InterviewIntegrationAdapter()
    success = await adapter.receive_evaluation(
        resume.id, job.id, {"workflow_run_id": 10, "call_disposition": call_disposition}
    )
    assert success is True

    stored = await _fetch_interview(db_session, job.id, resume.id)
    assert stored.status == "RESCHEDULE_PENDING"
    assert stored.outcome == call_disposition


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "call_disposition",
    ["user_hangup", "user_idle_max_duration_exceeded", "call_duration_exceeded", "system_cancelled", ""],
)
async def test_receive_evaluation_non_qualifying_dispositions_are_failed(
    call_disposition, setup_job_and_resume, db_session
):
    """user_hangup and idle/duration timeouts never auto-qualify for retry -
    they land here for manual recruiter review, per explicit design choice."""
    job, resume = setup_job_and_resume
    interview = Interview(job_id=job.id, resume_id=resume.id, status="SCHEDULED")
    db_session.add(interview)
    await db_session.commit()

    adapter = InterviewIntegrationAdapter()
    payload = {"workflow_run_id": 11}
    if call_disposition:
        payload["call_disposition"] = call_disposition
    success = await adapter.receive_evaluation(resume.id, job.id, payload)
    assert success is True

    stored = await _fetch_interview(db_session, job.id, resume.id)
    assert stored.status == "FAILED"


# -- attempt-generation fence: stale webhooks, idempotent redelivery, retry races --

@pytest.mark.asyncio
async def test_receive_evaluation_rejects_lower_run_id_as_stale(setup_job_and_resume, db_session):
    job, resume = setup_job_and_resume
    interview = Interview(job_id=job.id, resume_id=resume.id, status="SCHEDULED")
    db_session.add(interview)
    await db_session.commit()

    adapter = InterviewIntegrationAdapter()
    await adapter.receive_evaluation(
        resume.id, job.id, {"workflow_run_id": 20, "call_disposition": "pipeline_error"}
    )
    after_first = await _fetch_interview(db_session, job.id, resume.id)
    assert after_first.status == "RESCHEDULE_PENDING"
    assert after_first.provider_run_id == "20"

    # A stale/out-of-order delivery with a lower run id must not mutate anything.
    success = await adapter.receive_evaluation(
        resume.id, job.id, {"workflow_run_id": 5, "call_disposition": "end_call", "years_relevant_experience": "x"}
    )
    assert success is True

    unchanged = await _fetch_interview(db_session, job.id, resume.id)
    assert unchanged.status == "RESCHEDULE_PENDING"
    assert unchanged.outcome == "pipeline_error"
    assert unchanged.provider_run_id == "20"


@pytest.mark.asyncio
async def test_receive_evaluation_same_run_id_redelivery_is_idempotent(setup_job_and_resume, db_session):
    """Distinct from the stale-lower-run case: an equal run id with no retry
    since is a genuine redelivery, not a stale attempt, and must still be
    accepted (Dograh's own documented redelivery-on-retry behavior)."""
    job, resume = setup_job_and_resume
    interview = Interview(job_id=job.id, resume_id=resume.id, status="SCHEDULED")
    db_session.add(interview)
    await db_session.commit()

    adapter = InterviewIntegrationAdapter()
    payload = {"workflow_run_id": 30, "call_disposition": "pipeline_error"}
    await adapter.receive_evaluation(resume.id, job.id, payload)
    first = await _fetch_interview(db_session, job.id, resume.id)

    success = await adapter.receive_evaluation(resume.id, job.id, payload)
    assert success is True
    second = await _fetch_interview(db_session, job.id, resume.id)

    assert second.status == first.status == "RESCHEDULE_PENDING"
    assert second.provider_run_id == first.provider_run_id == "30"
    assert second.provider_run_attempt == first.provider_run_attempt == 0


@pytest.mark.asyncio
@patch("app.services.interview.outreach_service.on_interview_triggered", new_callable=AsyncMock)
async def test_retry_race_stale_old_attempt_webhook_rejected_after_retry(
    mock_outreach, setup_job_and_resume, db_session
):
    """The exact race from the plan: a retry is triggered before the old
    attempt's webhook (same or lower workflow_run_id) is redelivered.
    provider_run_id alone can't detect this since it hasn't moved yet - the
    provider_run_attempt-vs-retry_count fence must reject it anyway."""
    job, resume = setup_job_and_resume
    adapter = InterviewIntegrationAdapter()

    # Trigger the first attempt so an Interview row actually exists, then
    # simulate it failing with a system error - lands in RESCHEDULE_PENDING,
    # the one auto-set state that's actually retriable.
    await adapter.trigger_interview(resume.id, job.id)
    await adapter.receive_evaluation(
        resume.id, job.id, {"workflow_run_id": 100, "call_disposition": "pipeline_error"}
    )
    before_retry = await _fetch_interview(db_session, job.id, resume.id)
    assert before_retry.status == "RESCHEDULE_PENDING"
    assert before_retry.retry_count == 0
    assert before_retry.provider_run_attempt == 0

    # Recruiter retries - retry_count bumps, but provider_run_id/attempt are
    # deliberately left untouched until the new attempt's own webhook arrives.
    await adapter.trigger_interview(resume.id, job.id)
    after_retry = await _fetch_interview(db_session, job.id, resume.id)
    assert after_retry.status == "SCHEDULED"
    assert after_retry.retry_count == 1
    assert after_retry.provider_run_id == "100"
    assert after_retry.provider_run_attempt == 0

    # A stale redelivery of the FIRST attempt's webhook (same run id) arrives
    # after the retry - must be rejected, not reprocessed onto the new attempt.
    success = await adapter.receive_evaluation(
        resume.id, job.id, {"workflow_run_id": 100, "call_disposition": "pipeline_error"}
    )
    assert success is True
    still_scheduled = await _fetch_interview(db_session, job.id, resume.id)
    assert still_scheduled.status == "SCHEDULED"  # untouched by the stale webhook
    assert still_scheduled.provider_run_id == "100"
    assert still_scheduled.provider_run_attempt == 0

    # The new attempt's genuine first webhook (a higher run id) is accepted
    # and correctly updates provider_run_id/provider_run_attempt together.
    success = await adapter.receive_evaluation(
        resume.id, job.id, {"workflow_run_id": 101, "call_disposition": "end_call", "years_relevant_experience": "3 years"}
    )
    assert success is True
    completed = await _fetch_interview(db_session, job.id, resume.id)
    assert completed.status == "COMPLETED"
    assert completed.provider_run_id == "101"
    assert completed.provider_run_attempt == 1


# -- trigger_interview state table --------------------------------------------

@pytest.mark.asyncio
@patch("app.services.interview.outreach_service.on_interview_triggered", new_callable=AsyncMock)
async def test_trigger_interview_refuses_when_already_active(
    mock_outreach, setup_job_and_resume, db_session
):
    job, resume = setup_job_and_resume
    adapter = InterviewIntegrationAdapter()
    await adapter.trigger_interview(resume.id, job.id)  # SCHEDULED

    with pytest.raises(InterviewNotRetriableError):
        await adapter.trigger_interview(resume.id, job.id)


@pytest.mark.asyncio
@patch("app.services.interview.outreach_service.on_interview_triggered", new_callable=AsyncMock)
async def test_trigger_interview_refuses_when_in_progress(
    mock_outreach, setup_job_and_resume, db_session
):
    job, resume = setup_job_and_resume
    interview = Interview(job_id=job.id, resume_id=resume.id, status="IN_PROGRESS")
    db_session.add(interview)
    await db_session.commit()

    adapter = InterviewIntegrationAdapter()
    with pytest.raises(InterviewNotRetriableError):
        await adapter.trigger_interview(resume.id, job.id)


@pytest.mark.asyncio
@pytest.mark.parametrize("terminal_status", ["DECLINED", "COMPLETED", "NO_SHOW"])
async def test_trigger_interview_refuses_from_terminal_states(
    terminal_status, setup_job_and_resume, db_session
):
    job, resume = setup_job_and_resume
    interview = Interview(job_id=job.id, resume_id=resume.id, status=terminal_status)
    db_session.add(interview)
    await db_session.commit()

    adapter = InterviewIntegrationAdapter()
    with pytest.raises(InterviewNotRetriableError):
        await adapter.trigger_interview(resume.id, job.id)


@pytest.mark.asyncio
@patch("app.services.interview.outreach_service.on_interview_triggered", new_callable=AsyncMock)
@pytest.mark.parametrize("retriable_status", ["RESCHEDULE_PENDING", "FAILED"])
async def test_trigger_interview_retries_from_retriable_states_until_cap(
    mock_outreach, retriable_status, setup_job_and_resume, db_session
):
    job, resume = setup_job_and_resume
    interview = Interview(
        job_id=job.id, resume_id=resume.id, status=retriable_status, retry_count=0
    )
    db_session.add(interview)
    await db_session.commit()

    adapter = InterviewIntegrationAdapter()

    from app.core.config import settings
    max_attempts = settings.INTERVIEW_MAX_RETRY_ATTEMPTS

    for expected_retry_count in range(1, max_attempts + 1):
        success = await adapter.trigger_interview(resume.id, job.id)
        assert success is True
        current = await _fetch_interview(db_session, job.id, resume.id)
        assert current.status == "SCHEDULED"
        assert current.retry_count == expected_retry_count
        # Reset back to the retriable status to simulate another failed attempt,
        # without touching retry_count (which persists across attempts).
        current.status = retriable_status
        await db_session.commit()

    # Cap reached - one more retry must be refused.
    with pytest.raises(InterviewNotRetriableError):
        await adapter.trigger_interview(resume.id, job.id)
