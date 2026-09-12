import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient

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
