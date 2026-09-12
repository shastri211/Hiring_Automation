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
    interview = Interview(
        job_id=job.id, resume_id=resume.id, status="IN_PROGRESS", provider="dograh", provider_run_id="555"
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
        "gathered_context": {"call_disposition": "completed"},
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
