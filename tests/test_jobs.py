import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient
from sqlalchemy import select

@pytest.mark.asyncio
async def test_create_job(client: AsyncClient):
    job_data = {
        "title": "Software Engineer",
        "description": "Develop cool things",
        "required_skills": ["Python", "FastAPI"],
        "experience": {"min_years": 3}
    }
    response = await client.post("/jobs/", json=job_data)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Software Engineer"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_job_rejects_empty_description(client: AsyncClient):
    response = await client.post("/jobs/", json={"title": "Role", "description": ""})
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_job_rejects_whitespace_only_description(client: AsyncClient):
    response = await client.post("/jobs/", json={"title": "Role", "description": "   \n\t  "})
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_bootstrap_job_profile_falls_back_when_profile_is_empty_dict():
    """profile_job can return a technically-truthy dict where every
    meaningful field is empty/null (e.g. an LLM response with no useful
    content) - that must be treated the same as a profiling failure, not
    silently accepted as a valid profile."""
    from app.api.jobs import _bootstrap_job_profile_and_embedding
    from app.models.job import Job

    job = Job(id=3, title="Ghost Role", description="Build things")

    with patch(
        "app.api.jobs.profiler_service.profile_job",
        new_callable=AsyncMock,
        return_value={"role_summary": None, "required_skills": [], "preferred_skills": [], "responsibilities": [], "requirements": []},
    ), patch(
        "app.api.jobs.embedding_router.generate_embedding",
        new_callable=AsyncMock,
        side_effect=Exception("no embedding providers eligible"),
    ):
        await _bootstrap_job_profile_and_embedding(job)

    assert job.job_profile["title"] == "Ghost Role"
    assert job.job_profile["role_summary"] == "Build things"


@pytest.mark.asyncio
async def test_bootstrap_job_profile_falls_back_when_llm_unavailable():
    """profile_job raising (e.g. LLMExhaustionError with no providers configured)
    must not propagate - job creation should fall back to a minimal profile
    instead of 500ing, matching the resilience the embedding call already has."""
    from app.api.jobs import _bootstrap_job_profile_and_embedding
    from app.services.llm_provider import LLMExhaustionError
    from app.models.job import Job

    job = Job(id=1, title="Backend Engineer", description="Build APIs")

    with patch(
        "app.api.jobs.profiler_service.profile_job",
        new_callable=AsyncMock,
        side_effect=LLMExhaustionError("no providers configured"),
    ), patch(
        "app.api.jobs.embedding_router.generate_embedding",
        new_callable=AsyncMock,
        side_effect=Exception("no embedding providers eligible"),
    ):
        await _bootstrap_job_profile_and_embedding(job)

    assert job.job_profile["title"] == "Backend Engineer"
    assert job.job_profile["required_skills"] == []
    assert not hasattr(job, "embedding")  # never a real column; must not be set
    assert job.embedding_profile is None
    assert job.embedding_status == "FAILED"


@pytest.mark.asyncio
async def test_bootstrap_job_profile_pins_embedding_profile_on_success():
    from app.api.jobs import _bootstrap_job_profile_and_embedding
    from app.models.job import Job
    from app.services.model_registry import EmbeddingProfileConfig

    job = Job(id=2, title="Data Engineer", description="Build pipelines")

    fake_profile = EmbeddingProfileConfig(
        provider="local",
        model="sentence-transformers/all-MiniLM-L6-v2",
        dimensions=384,
        metric="Cosine",
        collection="resume_candidates_local_384",
        task_profile="resume_screening",
    )

    with patch(
        "app.api.jobs.profiler_service.profile_job",
        new_callable=AsyncMock,
        return_value={"title": "Data Engineer", "required_skills": ["SQL"]},
    ), patch(
        "app.api.jobs.embedding_router.generate_embedding",
        new_callable=AsyncMock,
        return_value=([0.1] * 384, fake_profile),
    ):
        await _bootstrap_job_profile_and_embedding(job)

    assert job.job_profile == {"title": "Data Engineer", "required_skills": ["SQL"]}
    assert job.embedding_profile == "sentence-transformers/all-MiniLM-L6-v2"
    assert job.embedding_status == "READY"
    assert not hasattr(job, "embedding")


@pytest.mark.asyncio
async def test_delete_job_cleans_up_correct_qdrant_collection(client: AsyncClient):
    """Deleting a job must resolve the real Qdrant collection via the model
    registry (not a made-up 'candidates_{profile}' string) and actually call
    delete_points_by_filter against it."""
    from app.api import jobs
    from app.main import app as fastapi_app
    from app.models.job import Job
    from app.services.model_registry import EmbeddingProfileConfig

    mock_db = AsyncMock()

    async def mock_get_db():
        yield mock_db

    fastapi_app.dependency_overrides[jobs.get_db] = mock_get_db

    job = MagicMock(spec=Job)
    job.id = 1
    job.embedding_profile = "sentence-transformers/all-MiniLM-L6-v2"

    job_exec = MagicMock()
    job_exec.scalar_one_or_none.return_value = job

    mock_db.execute = AsyncMock(side_effect=[job_exec] + [MagicMock()] * 5)
    mock_db.delete = AsyncMock()
    mock_db.commit = AsyncMock()

    fake_profile = EmbeddingProfileConfig(
        provider="local",
        model="sentence-transformers/all-MiniLM-L6-v2",
        dimensions=384,
        metric="Cosine",
        collection="resume_candidates_local_384",
        task_profile="resume_screening",
    )

    try:
        with patch(
            "app.api.jobs.model_registry.get_profile_by_model", return_value=fake_profile
        ), patch(
            "app.api.jobs.vector_store.delete_points_by_filter", new_callable=AsyncMock
        ) as mock_delete_points:
            response = await client.delete("/jobs/1")

        assert response.status_code == 204
        mock_delete_points.assert_awaited_once_with(
            "resume_candidates_local_384", {"job_id": 1}
        )
    finally:
        fastapi_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_trigger_screening_sets_batch_total_to_ready_resume_count(client: AsyncClient, db_session):
    """The screening-trigger batch must record how many candidates this run
    will actually screen (total_resumes) instead of defaulting to 0 forever -
    otherwise the cross-job Processing overview (/jobs/batches/overview)
    permanently shows a 0/0/0 row for every screening run."""
    from app.models.job import Job
    from app.models.resume import Resume
    from app.models.batch import ScreeningBatch
    import hashlib

    job = Job(
        title="Trigger Screening Job",
        description="Testing trigger_screening batch accounting",
        job_profile={"title": "Trigger Screening Job"},
        status="ACTIVE",
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    upload_batch = ScreeningBatch(job_id=job.id, total_resumes=2, processed=2)
    db_session.add(upload_batch)
    await db_session.commit()
    await db_session.refresh(upload_batch)

    for i in range(2):
        db_session.add(Resume(
            batch_id=upload_batch.id,
            job_id=job.id,
            filename=f"r{i}.pdf",
            file_hash=hashlib.sha256(f"trigger-screening-{i}".encode()).hexdigest(),
            storage_key=f"job_{job.id}/r{i}.pdf",
            status="READY",
        ))
    await db_session.commit()

    response = await client.post(f"/jobs/{job.id}/screen")
    assert response.status_code == 202
    batch_id = response.json()["batch_id"]

    check = await db_session.execute(
        select(ScreeningBatch).where(ScreeningBatch.id == batch_id)
    )
    screen_batch = check.scalar_one()
    assert screen_batch.total_resumes == 2


@pytest.mark.asyncio
async def test_get_batches_overview_returns_cross_job_batches(client: AsyncClient):
    """GET /jobs/batches/overview backs the sidebar "Processing" page: it must
    resolve before the /{job_id} routes (job_id is typed int, so a literal
    "batches" segment there would 422) and return each batch alongside its
    parent job's title/status using the batch's own stored counters."""
    from app.api import jobs
    from app.main import app as fastapi_app
    from app.models.batch import ScreeningBatch
    import datetime

    mock_db = AsyncMock()

    async def mock_get_db():
        yield mock_db

    fastapi_app.dependency_overrides[jobs.get_db] = mock_get_db

    batch = MagicMock(spec=ScreeningBatch)
    batch.id = 42
    batch.job_id = 7
    batch.status = "PROCESSING"
    batch.total_resumes = 15
    batch.processed = 9
    batch.failed = 1
    batch.created_at = datetime.datetime.utcnow()

    rows_exec = MagicMock()
    rows_exec.all.return_value = [(batch, "Backend Engineer", "ACTIVE")]
    mock_db.execute = AsyncMock(return_value=rows_exec)

    try:
        response = await client.get("/jobs/batches/overview")
        assert response.status_code == 200
        body = response.json()
        assert body == [{
            "job_id": 7,
            "job_title": "Backend Engineer",
            "job_status": "ACTIVE",
            "batch_id": 42,
            "batch_status": "PROCESSING",
            "total": 15,
            "processed": 9,
            "failed": 1,
            "created_at": body[0]["created_at"],
        }]
    finally:
        fastapi_app.dependency_overrides.clear()
