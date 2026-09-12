import json
from unittest.mock import patch, AsyncMock

import pytest
from sqlalchemy import select

from app.services.interview import InterviewIntegrationAdapter
from app.models.job import Job
from app.models.batch import ScreeningBatch
from app.models.resume import Resume
from app.models.interview import Interview


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
    job = Job(title="Test Job", description="A test job description")
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
async def test_trigger_interview_regenerates_token_on_retrigger(
    mock_outreach, setup_job_and_resume, db_session
):
    job, resume = setup_job_and_resume
    adapter = InterviewIntegrationAdapter()

    await adapter.trigger_interview(resume.id, job.id)
    first = await _fetch_interview(db_session, job.id, resume.id)
    first_token = first.public_token

    await adapter.trigger_interview(resume.id, job.id)
    second = await _fetch_interview(db_session, job.id, resume.id)

    assert second.public_token != first_token
    assert second.id == first.id  # same row, get-or-create - not a duplicate


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
    # renderer), not nested objects.
    payload = {
        "source": "dograh",
        "workflow_run_id": 555,
        "call_disposition": "completed",
        "gathered_context": json.dumps({"call_disposition": "completed", "sentiment": "positive"}),
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
    # JSON-string fields must be normalized back into real dicts.
    assert stored.evaluation["gathered_context"] == {
        "call_disposition": "completed",
        "sentiment": "positive",
    }
    assert stored.evaluation["cost_info"] == {"call_duration_seconds": 120}

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
    JSON strings - normalization must be a no-op in that case."""
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
    assert stored.evaluation["gathered_context"] == {"call_disposition": "completed"}
    assert stored.provider_run_id == "42"


@pytest.mark.asyncio
async def test_receive_evaluation_missing_interview_returns_false(db_session):
    adapter = InterviewIntegrationAdapter()
    success = await adapter.receive_evaluation(999999, 999999, {"score": 1})
    assert success is False
