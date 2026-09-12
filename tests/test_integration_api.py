import pytest
from httpx import AsyncClient
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
