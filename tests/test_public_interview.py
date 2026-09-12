import secrets
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from app.models.job import Job
from app.models.batch import ScreeningBatch
from app.models.resume import Resume
from app.models.profile import CandidateProfile
from app.models.interview import Interview


async def _make_job_resume(db_session, job_title="Backend Engineer", candidate_name="Jane Doe"):
    job = Job(title=job_title, description="A test job description")
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
        file_hash=f"hash_{secrets.token_hex(8)}",
        storage_key="key",
        status="PROCESSED",
    )
    db_session.add(resume)
    await db_session.commit()
    await db_session.refresh(resume)

    profile = CandidateProfile(resume_id=resume.id, name=candidate_name, email="jane@example.com")
    db_session.add(profile)
    await db_session.commit()

    return job, resume


async def _make_interview(db_session, job, resume, *, status="SCHEDULED", expires_delta=timedelta(hours=1)):
    interview = Interview(
        job_id=job.id,
        resume_id=resume.id,
        status=status,
        provider="dograh",
        public_token=secrets.token_urlsafe(32),
        link_expires_at=datetime.now(timezone.utc) + expires_delta if expires_delta is not None else None,
    )
    db_session.add(interview)
    await db_session.commit()
    await db_session.refresh(interview)
    return interview


@pytest.mark.asyncio
async def test_valid_token_returns_expected_fields(db_session, client: AsyncClient):
    job, resume = await _make_job_resume(db_session, job_title="Backend Engineer", candidate_name="Jane Doe")
    interview = await _make_interview(db_session, job, resume)

    response = await client.get(f"/public/interview/{interview.public_token}")
    assert response.status_code == 200
    body = response.json()

    assert body["candidate_name"] == "Jane Doe"
    assert body["job_title"] == "Backend Engineer"
    assert "dograh_base_url" in body
    assert "dograh_embed_token" in body
    assert "dograh_environment" in body
    assert "dograh_api_endpoint" in body
    assert body["initial_context"] == {
        "job_id": job.id,
        "resume_id": resume.id,
        "interview_id": interview.id,
    }


@pytest.mark.asyncio
async def test_unknown_token_returns_404_not_found(client: AsyncClient):
    response = await client.get("/public/interview/does-not-exist-token")
    assert response.status_code == 404
    assert response.json()["detail"]["reason"] == "not_found"


@pytest.mark.asyncio
async def test_expired_token_returns_410_expired(db_session, client: AsyncClient):
    job, resume = await _make_job_resume(db_session)
    interview = await _make_interview(db_session, job, resume, expires_delta=timedelta(hours=-1))

    response = await client.get(f"/public/interview/{interview.public_token}")
    assert response.status_code == 410
    assert response.json()["detail"]["reason"] == "expired"


@pytest.mark.asyncio
async def test_completed_interview_returns_410_already_completed(db_session, client: AsyncClient):
    job, resume = await _make_job_resume(db_session)
    interview = await _make_interview(db_session, job, resume, status="COMPLETED")

    response = await client.get(f"/public/interview/{interview.public_token}")
    assert response.status_code == 410
    assert response.json()["detail"]["reason"] == "already_completed"


@pytest.mark.asyncio
async def test_started_is_idempotent_and_transitions_scheduled_to_in_progress(
    db_session, client: AsyncClient
):
    job, resume = await _make_job_resume(db_session)
    interview = await _make_interview(db_session, job, resume, status="SCHEDULED")

    first = await client.post(f"/public/interview/{interview.public_token}/started")
    assert first.status_code == 200
    assert first.json() == {"success": True}

    get_after_first = await client.get(f"/public/interview/{interview.public_token}")
    assert get_after_first.status_code == 200  # IN_PROGRESS is not COMPLETED, still visitable

    second = await client.post(f"/public/interview/{interview.public_token}/started")
    assert second.status_code == 200
    assert second.json() == {"success": True}


@pytest.mark.asyncio
async def test_started_on_completed_interview_still_returns_410(db_session, client: AsyncClient):
    job, resume = await _make_job_resume(db_session)
    interview = await _make_interview(db_session, job, resume, status="COMPLETED")

    response = await client.post(f"/public/interview/{interview.public_token}/started")
    assert response.status_code == 410
    assert response.json()["detail"]["reason"] == "already_completed"


@pytest.mark.asyncio
async def test_token_never_leaks_another_candidates_data(db_session, client: AsyncClient):
    job_a, resume_a = await _make_job_resume(db_session, job_title="Job A", candidate_name="Alice")
    interview_a = await _make_interview(db_session, job_a, resume_a)

    job_b, resume_b = await _make_job_resume(db_session, job_title="Job B", candidate_name="Bob")
    interview_b = await _make_interview(db_session, job_b, resume_b)

    response_a = await client.get(f"/public/interview/{interview_a.public_token}")
    body_a = response_a.json()

    assert body_a["candidate_name"] == "Alice"
    assert body_a["job_title"] == "Job A"
    assert body_a["initial_context"]["resume_id"] == resume_a.id
    assert body_a["initial_context"]["job_id"] == job_a.id

    # Never Bob's data under Alice's token.
    assert body_a["candidate_name"] != "Bob"
    assert body_a["job_title"] != "Job B"
    assert body_a["initial_context"]["resume_id"] != resume_b.id
    assert body_a["initial_context"]["job_id"] != job_b.id
