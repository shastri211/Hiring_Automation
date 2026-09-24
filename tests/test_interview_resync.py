from unittest.mock import patch, AsyncMock

import pytest
from httpx import AsyncClient

from app.models.job import Job
from app.models.batch import ScreeningBatch
from app.models.resume import Resume
from app.models.interview import Interview


@pytest.fixture
async def setup_data(db_session):
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
        filename="resume.pdf",
        file_hash="dummy_hash_resync",
        storage_key="dummy_key",
        status="PROCESSED",
    )
    db_session.add(resume)
    await db_session.commit()
    await db_session.refresh(resume)

    return job, resume


@pytest.mark.asyncio
async def test_resync_returns_400_when_no_interview(setup_data, client: AsyncClient):
    job, resume = setup_data
    response = await client.post(f"/jobs/{job.id}/interviews/{resume.id}/resync")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_resync_returns_400_when_no_run_recorded_yet(setup_data, db_session, client: AsyncClient):
    job, resume = setup_data
    interview = Interview(job_id=job.id, resume_id=resume.id, status="SCHEDULED", provider="dograh")
    db_session.add(interview)
    await db_session.commit()

    response = await client.post(f"/jobs/{job.id}/interviews/{resume.id}/resync")
    assert response.status_code == 400
    assert "no run recorded" in response.json()["detail"].lower() or "run" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_resync_returns_400_when_workflow_id_not_configured(setup_data, db_session, client: AsyncClient):
    job, resume = setup_data
    interview = Interview(
        job_id=job.id, resume_id=resume.id, status="IN_PROGRESS", provider="dograh", provider_run_id="123"
    )
    db_session.add(interview)
    await db_session.commit()

    with patch("app.api.jobs.settings.DOGRAH_WORKFLOW_ID", None):
        response = await client.post(f"/jobs/{job.id}/interviews/{resume.id}/resync")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_resync_success_applies_run_data(setup_data, db_session, client: AsyncClient):
    job, resume = setup_data
    # provider_run_attempt matches retry_count (0), reflecting an already-
    # consistent row (same invariant the migration backfill maintains for
    # pre-existing production rows) - otherwise the attempt-generation guard
    # would treat this run's own resync as stale.
    interview = Interview(
        job_id=job.id, resume_id=resume.id, status="IN_PROGRESS", provider="dograh",
        provider_run_id="555", provider_run_attempt=0,
    )
    db_session.add(interview)
    await db_session.commit()

    run_data = {
        "id": 555,
        "is_completed": True,
        "transcript_url": "https://dograh.example.com/t/555",
        "recording_url": "https://dograh.example.com/r/555",
        "user_recording_url": None,
        "bot_recording_url": None,
        # "end_call" + a populated interview-stage field is the real,
        # confirmed disposition/evidence pair for a genuinely completed
        # web interview (see app/services/interview.py).
        "gathered_context": {"call_disposition": "end_call", "years_relevant_experience": "5 years"},
        "cost_info": {"call_duration_seconds": 90},
    }

    with patch("app.api.jobs.settings.DOGRAH_WORKFLOW_ID", "7"), patch(
        "app.api.jobs.dograh_client.get_run", new_callable=AsyncMock
    ) as mock_get_run:
        mock_get_run.return_value = run_data
        response = await client.post(f"/jobs/{job.id}/interviews/{resume.id}/resync")

    assert response.status_code == 200
    assert response.json()["success"] is True
    mock_get_run.assert_awaited_once_with("7", "555")

    detail = await client.get(f"/jobs/{job.id}/results/{resume.id}")
    interview_detail = detail.json()["interview"]
    assert interview_detail["status"] == "COMPLETED"
    assert interview_detail["transcript_url"] == "https://dograh.example.com/t/555"
    assert interview_detail["recording_url"] == "https://dograh.example.com/r/555"


@pytest.mark.asyncio
async def test_resync_returns_502_on_dograh_failure(setup_data, db_session, client: AsyncClient):
    job, resume = setup_data
    interview = Interview(
        job_id=job.id, resume_id=resume.id, status="IN_PROGRESS", provider="dograh", provider_run_id="555"
    )
    db_session.add(interview)
    await db_session.commit()

    with patch("app.api.jobs.settings.DOGRAH_WORKFLOW_ID", "7"), patch(
        "app.api.jobs.dograh_client.get_run", new_callable=AsyncMock
    ) as mock_get_run:
        mock_get_run.side_effect = Exception("network boom")
        response = await client.post(f"/jobs/{job.id}/interviews/{resume.id}/resync")

    assert response.status_code == 502


@pytest.mark.asyncio
async def test_resync_after_retry_operates_on_latest_attempt(setup_data, db_session, client: AsyncClient):
    """After a retry, provider_run_id points at the new attempt (once its own
    webhook has been recorded) - resync must fetch and apply *that* run, not
    the first attempt's, even though it reuses the same Interview row."""
    job, resume = setup_data
    interview = Interview(
        job_id=job.id, resume_id=resume.id, status="RESCHEDULE_PENDING",
        provider="dograh", provider_run_id="555", provider_run_attempt=0, retry_count=0,
    )
    db_session.add(interview)
    await db_session.commit()

    # Recruiter retries via trigger - retry_count bumps to 1, provider_run_id
    # stays at 555 until the new attempt's own webhook arrives.
    trigger_response = await client.post(
        "/integration/interview/trigger", json={"job_id": job.id, "resume_id": resume.id}
    )
    assert trigger_response.status_code == 200

    # The new attempt's own webhook arrives, recording run 600 as current.
    webhook_response = await client.post("/integration/interview/evaluation", json={
        "job_id": job.id,
        "resume_id": resume.id,
        "evaluation_data": {"workflow_run_id": 600},
        "call_disposition": "pipeline_error",
    })
    assert webhook_response.status_code == 200

    detail = await client.get(f"/jobs/{job.id}/results/{resume.id}")
    assert detail.json()["interview"]["status"] == "RESCHEDULE_PENDING"

    run_data = {
        "id": 600,
        "is_completed": True,
        "transcript_url": "https://dograh.example.com/t/600",
        "recording_url": None,
        "user_recording_url": None,
        "bot_recording_url": None,
        "gathered_context": {"call_disposition": "end_call", "years_relevant_experience": "2 years"},
        "cost_info": {"call_duration_seconds": 45},
    }
    with patch("app.api.jobs.settings.DOGRAH_WORKFLOW_ID", "7"), patch(
        "app.api.jobs.dograh_client.get_run", new_callable=AsyncMock
    ) as mock_get_run:
        mock_get_run.return_value = run_data
        resync_response = await client.post(f"/jobs/{job.id}/interviews/{resume.id}/resync")

    assert resync_response.status_code == 200
    # Confirms resync read the *current* (post-retry) provider_run_id, 600 -
    # not 555, the superseded first attempt.
    mock_get_run.assert_awaited_once_with("7", "600")

    final = await client.get(f"/jobs/{job.id}/results/{resume.id}")
    assert final.json()["interview"]["status"] == "COMPLETED"
    assert final.json()["interview"]["transcript_url"] == "https://dograh.example.com/t/600"


# -- manual decline -----------------------------------------------------------

@pytest.mark.asyncio
async def test_decline_returns_404_when_no_interview(setup_data, client: AsyncClient):
    job, resume = setup_data
    response = await client.post(f"/jobs/{job.id}/interviews/{resume.id}/decline")
    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("terminal_status", ["COMPLETED", "DECLINED", "NO_SHOW"])
async def test_decline_returns_400_from_terminal_states(
    terminal_status, setup_data, db_session, client: AsyncClient
):
    job, resume = setup_data
    interview = Interview(job_id=job.id, resume_id=resume.id, status=terminal_status)
    db_session.add(interview)
    await db_session.commit()

    response = await client.post(f"/jobs/{job.id}/interviews/{resume.id}/decline")
    assert response.status_code == 400


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "non_terminal_status", ["PENDING", "SCHEDULED", "IN_PROGRESS", "RESCHEDULE_PENDING", "FAILED"]
)
async def test_decline_succeeds_from_non_terminal_states(
    non_terminal_status, setup_data, db_session, client: AsyncClient
):
    job, resume = setup_data
    interview = Interview(job_id=job.id, resume_id=resume.id, status=non_terminal_status)
    db_session.add(interview)
    await db_session.commit()

    response = await client.post(f"/jobs/{job.id}/interviews/{resume.id}/decline")
    assert response.status_code == 200

    detail = await client.get(f"/jobs/{job.id}/results/{resume.id}")
    interview_detail = detail.json()["interview"]
    assert interview_detail["status"] == "DECLINED"
    assert interview_detail["outcome"] == "manual_decline"
