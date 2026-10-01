import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient
from sqlalchemy import select
from tenancy_fixtures import TEST_ORG_ID

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

    job = Job(organization_id=TEST_ORG_ID, id=3, title="Ghost Role", description="Build things")

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

    job = Job(organization_id=TEST_ORG_ID, id=1, title="Backend Engineer", description="Build APIs")

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

    job = Job(organization_id=TEST_ORG_ID, id=2, title="Data Engineer", description="Build pipelines")

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

    # job lookup + one delete()/update() per statement in delete_job's
    # cascade (see app/api/jobs.py): DecisionAudit, ScreeningResult,
    # EmailMessage, TalentPoolEntry (delete), TalentPoolEntry (SET NULL
    # added_from_job_id), CandidateMatchSuggestion, ApplicationResumeHistory,
    # Application, CandidateProfile, PublicApplicationSubmission, Interview,
    # Resume, ScreeningBatch.
    mock_db.execute = AsyncMock(side_effect=[job_exec] + [MagicMock()] * 13)
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
        organization_id=TEST_ORG_ID,
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
    parent job's title/status. For an UPLOAD batch, total/processed/failed
    are computed live from current Resume rows (not the batch's own
    total_resumes/processed/failed snapshot columns, which go stale if a
    resume is later deleted out from under the batch - see
    app/api/jobs.py::get_batches_overview)."""
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
    batch.batch_type = "UPLOAD"
    batch.total_resumes = 15  # stale snapshot - must NOT be what's returned
    batch.processed = 999
    batch.failed = 999
    batch.created_at = datetime.datetime.utcnow()

    rows_exec = MagicMock()
    rows_exec.all.return_value = [(batch, "Backend Engineer", "ACTIVE")]

    # Live per-status resume counts for this batch: 9 READY, 1 FAILED, 5
    # still UPLOADED - total 15, matching the stale snapshot here on purpose
    # so a naive "did it change" assertion wouldn't catch a regression back
    # to reading the snapshot column.
    counts_exec = MagicMock()
    counts_exec.all.return_value = [(42, "READY", 9), (42, "FAILED", 1), (42, "UPLOADED", 5)]

    mock_db.execute = AsyncMock(side_effect=[rows_exec, counts_exec])

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
            "batch_type": "UPLOAD",
        }]
    finally:
        fastapi_app.dependency_overrides.clear()


# -- manual embedding-profile migration trigger --------------------------------
# migration_service.migrate_job_embedding_profile's worker handler
# ("migrate_job") previously had no caller anywhere in the codebase - this is
# the missing trigger, mirroring trigger_screening's manual-enqueue pattern.

@pytest.mark.asyncio
async def test_trigger_embedding_migration_returns_404_for_missing_job(client: AsyncClient):
    response = await client.post("/jobs/999999/migrate-embedding-profile")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_trigger_embedding_migration_returns_409_when_already_migrating(client: AsyncClient, db_session):
    from app.models.job import Job

    job = Job(organization_id=TEST_ORG_ID, title="Already Migrating Job", description="d", embedding_status="MIGRATING")
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    response = await client.post(f"/jobs/{job.id}/migrate-embedding-profile")
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_trigger_embedding_migration_enqueues_task(client: AsyncClient, db_session):
    from app.models.job import Job

    job = Job(organization_id=TEST_ORG_ID, title="Migrate Me Job", description="d", embedding_status="READY", embedding_profile="old-profile")
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    with patch("app.api.jobs.queue_service.enqueue_task", new_callable=AsyncMock) as mock_enqueue:
        response = await client.post(f"/jobs/{job.id}/migrate-embedding-profile")

    assert response.status_code == 202
    mock_enqueue.assert_awaited_once_with({"action": "migrate_job", "job_id": job.id})


@pytest.mark.asyncio
async def test_trigger_embedding_migration_returns_502_on_enqueue_failure(client: AsyncClient, db_session):
    from app.models.job import Job

    job = Job(organization_id=TEST_ORG_ID, title="Migrate Me Failing Job", description="d", embedding_status="READY")
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    with patch("app.api.jobs.queue_service.enqueue_task", new_callable=AsyncMock) as mock_enqueue:
        mock_enqueue.side_effect = Exception("redis unavailable")
        response = await client.post(f"/jobs/{job.id}/migrate-embedding-profile")

    assert response.status_code == 502


@pytest.mark.asyncio
async def test_upload_job_extracts_from_private_temp_file_and_deletes_it(client: AsyncClient):
    """Two same-named JD uploads must never share a path (another
    organization's upload could otherwise be read mid-extraction), and the
    file must not outlive extraction - only its text is kept."""
    import os
    seen_paths = []

    class _RecordingExtractor:
        async def extract(self, file_path):
            with open(file_path, "rb") as f:
                assert f.read() == b"%PDF-fake"
            seen_paths.append(file_path)
            return "Senior backend engineer building Python services."

    with patch("app.api.jobs.get_extractor", return_value=_RecordingExtractor()), \
         patch("app.api.jobs._bootstrap_job_profile_and_embedding", new_callable=AsyncMock):
        for _ in range(2):
            response = await client.post(
                "/jobs/upload",
                data={"title": "Backend"},
                files={"file": ("jd.pdf", b"%PDF-fake", "application/pdf")},
            )
            assert response.status_code == 201
            assert "Python services" in response.json()["description"]

    assert len(set(seen_paths)) == 2
    for path in seen_paths:
        assert path.endswith(".pdf")
        assert not os.path.exists(path)


@pytest.mark.asyncio
async def test_upload_job_deletes_temp_file_when_extraction_fails(client: AsyncClient):
    import os
    seen_paths = []

    class _FailingExtractor:
        async def extract(self, file_path):
            seen_paths.append(file_path)
            raise ValueError("corrupt")

    with patch("app.api.jobs.get_extractor", return_value=_FailingExtractor()):
        response = await client.post(
            "/jobs/upload",
            data={"title": "Backend"},
            files={"file": ("jd.pdf", b"%PDF-fake", "application/pdf")},
        )
    assert response.status_code == 400
    assert seen_paths and not os.path.exists(seen_paths[0])


@pytest.mark.asyncio
async def test_batch_progress_counts_are_per_batch_and_unscreened_is_exact(client: AsyncClient, db_session):
    """Each batch reports only its own decisions (a screening run: the
    results it created; an upload batch: its own resumes), and `unscreened`
    counts READY resumes with no result - previously every batch repeated
    the job-wide totals and the page derived "unscreened" by summing them,
    which hid unscreened resumes once a job had several batches."""
    from app.models.job import Job
    from app.models.resume import Resume
    from app.models.batch import ScreeningBatch
    from app.models.screening import ScreeningResult
    import secrets as _secrets

    job = Job(organization_id=TEST_ORG_ID, title="Progress", description="Progress counts", job_profile={"title": "P"})
    db_session.add(job)
    await db_session.flush()
    upload_1 = ScreeningBatch(job_id=job.id, batch_type="UPLOAD", status="COMPLETED", total_resumes=2)
    screen_1 = ScreeningBatch(job_id=job.id, batch_type="SCREEN", status="COMPLETED", total_resumes=2, processed=2)
    upload_2 = ScreeningBatch(job_id=job.id, batch_type="UPLOAD", status="COMPLETED", total_resumes=3)
    screen_2 = ScreeningBatch(job_id=job.id, batch_type="SCREEN", status="PROCESSING", total_resumes=2)
    db_session.add_all([upload_1, screen_1, upload_2, screen_2])
    await db_session.flush()

    def _resume(batch, status):
        return Resume(
            job_id=job.id, batch_id=batch.id, filename="r.pdf", file_hash=_secrets.token_hex(16),
            storage_key="k", status=status,
        )
    r1, r2 = _resume(upload_1, "READY"), _resume(upload_1, "READY")
    r3, r4, r5 = _resume(upload_2, "READY"), _resume(upload_2, "READY"), _resume(upload_2, "FAILED")
    db_session.add_all([r1, r2, r3, r4, r5])
    await db_session.flush()
    db_session.add_all([
        ScreeningResult(job_id=job.id, resume_id=r1.id, screening_batch_id=screen_1.id, score=90, decision="SHORTLIST"),
        ScreeningResult(job_id=job.id, resume_id=r2.id, screening_batch_id=screen_1.id, decision="PRE_SCREENED_OUT"),
    ])
    await db_session.commit()

    response = await client.get(f"/jobs/{job.id}/progress")
    assert response.status_code == 200
    data = response.json()
    assert data["unscreened"] == 2
    by_id = {b["batch_id"]: b for b in data["batches"]}

    assert (by_id[screen_1.id]["shortlisted"], by_id[screen_1.id]["pre_screened_out"]) == (1, 1)
    assert (by_id[screen_2.id]["shortlisted"], by_id[screen_2.id]["pre_screened_out"]) == (0, 0)
    assert by_id[screen_1.id]["total"] == 2 and by_id[screen_1.id]["completed"] == 2

    assert (by_id[upload_1.id]["shortlisted"], by_id[upload_1.id]["pre_screened_out"]) == (1, 1)
    assert by_id[upload_2.id]["shortlisted"] == 0
    assert (by_id[upload_2.id]["total"], by_id[upload_2.id]["completed"], by_id[upload_2.id]["failed"]) == (3, 2, 1)


def _delete_job_mocks():
    from app.models.job import Job
    from app.services.model_registry import EmbeddingProfileConfig

    mock_db = AsyncMock()
    job = MagicMock(spec=Job)
    job.id = 1
    job.embedding_profile = "sentence-transformers/all-MiniLM-L6-v2"
    job_exec = MagicMock()
    job_exec.scalar_one_or_none.return_value = job
    mock_db.execute = AsyncMock(side_effect=[job_exec] + [MagicMock()] * 13)
    mock_db.delete = AsyncMock()
    profile = EmbeddingProfileConfig(
        provider="local", model=job.embedding_profile, dimensions=384, metric="Cosine",
        collection="resume_candidates_local_384", task_profile="resume_screening",
    )
    return mock_db, profile


@pytest.mark.asyncio
async def test_delete_job_removes_vectors_and_files_only_after_commit(client: AsyncClient, tmp_path):
    """If the DB commit fails, the job's rows survive - so its vectors and
    stored resume files must survive too. Cleanup runs after the commit."""
    from app.api import jobs
    from app.main import app as fastapi_app

    (tmp_path / "job_1").mkdir()
    order = []
    mock_db, profile = _delete_job_mocks()

    async def mock_get_db():
        yield mock_db

    fastapi_app.dependency_overrides[jobs.get_db] = mock_get_db
    try:
        with patch("app.api.jobs.model_registry.get_profile_by_model", return_value=profile), \
             patch("app.api.jobs.settings.STORAGE_LOCAL_DIR", str(tmp_path)), \
             patch("app.api.jobs.vector_store.delete_points_by_filter", new_callable=AsyncMock) as mock_delete_points:
            mock_db.commit = AsyncMock(side_effect=RuntimeError("commit failed"))
            with pytest.raises(RuntimeError):
                await client.delete("/jobs/1")
            mock_delete_points.assert_not_awaited()
            assert (tmp_path / "job_1").exists()

            mock_db.execute = _delete_job_mocks()[0].execute
            mock_db.commit = AsyncMock(side_effect=lambda: order.append("commit"))
            mock_delete_points.side_effect = lambda *a, **k: order.append("vectors")
            response = await client.delete("/jobs/1")

        assert response.status_code == 204
        assert order == ["commit", "vectors"]
        assert not (tmp_path / "job_1").exists()
    finally:
        fastapi_app.dependency_overrides.clear()
