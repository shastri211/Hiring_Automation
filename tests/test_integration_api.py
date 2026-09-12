import base64

import pytest
from httpx import AsyncClient
from unittest.mock import patch

from app.main import app
from app.models.resume import Resume
from app.models.job import Job
from app.models.interview import Interview
from app.models.batch import ScreeningBatch

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
        filename="test_resume.pdf",
        file_hash="dummy_hash",
        storage_key="dummy_key",
        status="PROCESSED"
    )
    db_session.add(resume)
    await db_session.commit()
    await db_session.refresh(resume)

    return job, resume

@pytest.mark.asyncio
async def test_trigger_interview(setup_data, client: AsyncClient):
    job, resume = setup_data
    response = await client.post("/integration/interview/trigger", json={
        "job_id": job.id,
        "resume_id": resume.id
    })
    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "Interview triggered successfully"}

@pytest.mark.asyncio
async def test_trigger_interview_invalid_ownership(setup_data, client: AsyncClient):
    job, resume = setup_data
    response = await client.post("/integration/interview/trigger", json={
        "job_id": job.id + 100,  # Invalid job id
        "resume_id": resume.id
    })
    assert response.status_code == 404
    assert "Resume not found for this job" in response.json()["detail"]

@pytest.mark.asyncio
async def test_update_interview_status(setup_data, db_session, client: AsyncClient):
    job, resume = setup_data
    # First trigger it
    await client.post("/integration/interview/trigger", json={
        "job_id": job.id,
        "resume_id": resume.id
    })
    
    # Then update status
    response = await client.post("/integration/interview/status", json={
        "job_id": job.id,
        "resume_id": resume.id,
        "status": "IN_PROGRESS"
    })
    assert response.status_code == 200
    assert response.json()["success"] is True

@pytest.mark.asyncio
async def test_update_interview_status_idempotent(setup_data, db_session, client: AsyncClient):
    job, resume = setup_data
    await client.post("/integration/interview/trigger", json={
        "job_id": job.id,
        "resume_id": resume.id
    })
    # Repeated deliveries
    await client.post("/integration/interview/status", json={
        "job_id": job.id, "resume_id": resume.id, "status": "IN_PROGRESS"
    })
    response = await client.post("/integration/interview/status", json={
        "job_id": job.id, "resume_id": resume.id, "status": "IN_PROGRESS"
    })
    assert response.status_code == 200
    assert response.json()["success"] is True

@pytest.mark.asyncio
async def test_update_interview_status_missing(setup_data, client: AsyncClient):
    job, resume = setup_data
    # We do NOT trigger it, so the interview record doesn't exist
    response = await client.post("/integration/interview/status", json={
        "job_id": job.id,
        "resume_id": resume.id,
        "status": "IN_PROGRESS"
    })
    assert response.status_code == 404
    assert "Interview not found for this candidate" in response.json()["detail"]

@pytest.mark.asyncio
async def test_receive_transcript(setup_data, client: AsyncClient):
    job, resume = setup_data
    await client.post("/integration/interview/trigger", json={"job_id": job.id, "resume_id": resume.id})
    
    response = await client.post("/integration/interview/transcript", json={
        "job_id": job.id,
        "resume_id": resume.id,
        "transcript": "Hello, how are you?"
    })
    assert response.status_code == 200
    assert response.json()["success"] is True

@pytest.mark.asyncio
async def test_receive_evaluation(setup_data, client: AsyncClient):
    job, resume = setup_data
    await client.post("/integration/interview/trigger", json={"job_id": job.id, "resume_id": resume.id})
    
    response = await client.post("/integration/interview/evaluation", json={
        "job_id": job.id,
        "resume_id": resume.id,
        "evaluation_data": {"score": 85, "notes": "Good candidate"}
    })
    assert response.status_code == 200
    assert response.json()["success"] is True


# -- A10: webhook auth (Dograh -> us) on status/transcript/evaluation ----------
# /interview/trigger is unaffected (only our own frontend calls it, tested
# above with no auth headers and still passing).

WEBHOOK_ENDPOINTS = [
    ("/integration/interview/status", {"status": "IN_PROGRESS"}),
    ("/integration/interview/transcript", {"transcript": "hello"}),
    ("/integration/interview/evaluation", {"evaluation_data": {"score": 1}}),
]


def _settings_patch(**overrides):
    return [patch(f"app.api.integration.settings.{k}", v) for k in overrides for v in [overrides[k]]]


class _Patched:
    def __init__(self, patchers):
        self.patchers = patchers

    def __enter__(self):
        for p in self.patchers:
            p.start()

    def __exit__(self, *a):
        for p in self.patchers:
            p.stop()


def webhook_auth(**overrides):
    return _Patched(_settings_patch(**overrides))


@pytest.mark.asyncio
async def test_webhook_auth_none_accepts_no_header(setup_data, client: AsyncClient):
    job, resume = setup_data
    await client.post("/integration/interview/trigger", json={"job_id": job.id, "resume_id": resume.id})

    with webhook_auth(DOGRAH_WEBHOOK_AUTH_TYPE="none", DOGRAH_WEBHOOK_SECRET=None):
        for path, extra in WEBHOOK_ENDPOINTS:
            response = await client.post(path, json={"job_id": job.id, "resume_id": resume.id, **extra})
            assert response.status_code == 200, path


@pytest.mark.asyncio
async def test_webhook_auth_api_key_accepts_valid_rejects_invalid_and_missing(
    setup_data, client: AsyncClient
):
    job, resume = setup_data
    await client.post("/integration/interview/trigger", json={"job_id": job.id, "resume_id": resume.id})

    with webhook_auth(
        DOGRAH_WEBHOOK_AUTH_TYPE="api_key",
        DOGRAH_WEBHOOK_HEADER_NAME="X-API-Key",
        DOGRAH_WEBHOOK_SECRET="s3cret",
    ):
        for path, extra in WEBHOOK_ENDPOINTS:
            body = {"job_id": job.id, "resume_id": resume.id, **extra}

            ok = await client.post(path, json=body, headers={"X-API-Key": "s3cret"})
            assert ok.status_code == 200, path

            wrong = await client.post(path, json=body, headers={"X-API-Key": "wrong"})
            assert wrong.status_code == 401, path

            missing = await client.post(path, json=body)
            assert missing.status_code == 401, path


@pytest.mark.asyncio
async def test_webhook_auth_bearer_token_accepts_valid_rejects_invalid_and_missing(
    setup_data, client: AsyncClient
):
    job, resume = setup_data
    await client.post("/integration/interview/trigger", json={"job_id": job.id, "resume_id": resume.id})

    with webhook_auth(DOGRAH_WEBHOOK_AUTH_TYPE="bearer_token", DOGRAH_WEBHOOK_SECRET="tok123"):
        for path, extra in WEBHOOK_ENDPOINTS:
            body = {"job_id": job.id, "resume_id": resume.id, **extra}

            ok = await client.post(path, json=body, headers={"Authorization": "Bearer tok123"})
            assert ok.status_code == 200, path

            wrong = await client.post(path, json=body, headers={"Authorization": "Bearer wrong"})
            assert wrong.status_code == 401, path

            missing = await client.post(path, json=body)
            assert missing.status_code == 401, path


@pytest.mark.asyncio
async def test_webhook_auth_basic_auth_accepts_valid_rejects_invalid_and_missing(
    setup_data, client: AsyncClient
):
    job, resume = setup_data
    await client.post("/integration/interview/trigger", json={"job_id": job.id, "resume_id": resume.id})

    valid_creds = base64.b64encode(b"dograh:hunter2").decode("ascii")
    wrong_creds = base64.b64encode(b"dograh:wrongpass").decode("ascii")

    with webhook_auth(DOGRAH_WEBHOOK_AUTH_TYPE="basic_auth", DOGRAH_WEBHOOK_SECRET="dograh:hunter2"):
        for path, extra in WEBHOOK_ENDPOINTS:
            body = {"job_id": job.id, "resume_id": resume.id, **extra}

            ok = await client.post(path, json=body, headers={"Authorization": f"Basic {valid_creds}"})
            assert ok.status_code == 200, path

            wrong = await client.post(path, json=body, headers={"Authorization": f"Basic {wrong_creds}"})
            assert wrong.status_code == 401, path

            missing = await client.post(path, json=body)
            assert missing.status_code == 401, path


@pytest.mark.asyncio
async def test_webhook_auth_custom_header_accepts_valid_rejects_invalid_and_missing(
    setup_data, client: AsyncClient
):
    job, resume = setup_data
    await client.post("/integration/interview/trigger", json={"job_id": job.id, "resume_id": resume.id})

    with webhook_auth(
        DOGRAH_WEBHOOK_AUTH_TYPE="custom_header",
        DOGRAH_WEBHOOK_HEADER_NAME="X-Dograh-Signature",
        DOGRAH_WEBHOOK_SECRET="custom-secret-value",
    ):
        for path, extra in WEBHOOK_ENDPOINTS:
            body = {"job_id": job.id, "resume_id": resume.id, **extra}

            ok = await client.post(
                path, json=body, headers={"X-Dograh-Signature": "custom-secret-value"}
            )
            assert ok.status_code == 200, path

            wrong = await client.post(
                path, json=body, headers={"X-Dograh-Signature": "not-it"}
            )
            assert wrong.status_code == 401, path

            missing = await client.post(path, json=body)
            assert missing.status_code == 401, path


@pytest.mark.asyncio
async def test_trigger_endpoint_never_requires_webhook_auth(setup_data, client: AsyncClient):
    """/interview/trigger is called only by our own frontend, never by Dograh -
    it must stay unauthenticated regardless of DOGRAH_WEBHOOK_AUTH_TYPE."""
    job, resume = setup_data
    with webhook_auth(DOGRAH_WEBHOOK_AUTH_TYPE="api_key", DOGRAH_WEBHOOK_SECRET="s3cret"):
        response = await client.post(
            "/integration/interview/trigger", json={"job_id": job.id, "resume_id": resume.id}
        )
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_webhook_evaluation_redelivery_is_idempotent(setup_data, client: AsyncClient):
    job, resume = setup_data
    await client.post("/integration/interview/trigger", json={"job_id": job.id, "resume_id": resume.id})

    payload = {
        "job_id": job.id,
        "resume_id": resume.id,
        "evaluation_data": {"workflow_run_id": 777, "score": 85},
    }
    first = await client.post("/integration/interview/evaluation", json=payload)
    assert first.status_code == 200

    detail_first = await client.get(f"/jobs/{job.id}/results/{resume.id}")
    completed_at_first = detail_first.json()["interview"]["completed_at"]
    assert completed_at_first is not None

    second = await client.post("/integration/interview/evaluation", json=payload)
    assert second.status_code == 200

    detail_second = await client.get(f"/jobs/{job.id}/results/{resume.id}")
    completed_at_second = detail_second.json()["interview"]["completed_at"]
    assert completed_at_second == completed_at_first
    assert detail_second.json()["interview"]["provider_run_id"] == "777"
