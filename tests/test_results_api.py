"""Phase 4: Tests for results API � pagination, filtering, sorting, batch progress,
candidate detail, and idempotent screening results."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock, ANY
from httpx import AsyncClient
from sqlalchemy import select

# -- Helpers --------------------------------------------------------------------

def _make_screening_result(job_id=1, resume_id=1, score=85.0, decision="SHORTLIST"):
    from app.models.screening import ScreeningResult
    sr = MagicMock(spec=ScreeningResult)
    sr.id = 1
    sr.job_id = job_id
    sr.resume_id = resume_id
    sr.score = score
    sr.decision = decision
    sr.strengths = ["Python"]
    sr.gaps = []
    sr.evidence = ["5 years Python experience"]
    import datetime
    sr.created_at = datetime.datetime.utcnow()
    return sr


def _make_resume(id=1, job_id=1, filename="test.pdf", status="READY", batch_id=1):
    from app.models.resume import Resume
    r = MagicMock(spec=Resume)
    r.id = id
    r.job_id = job_id
    r.batch_id = batch_id
    r.filename = filename
    r.status = status
    r.error_message = None
    return r


def _make_job(id=1, title="SWE"):
    from app.models.job import Job
    j = MagicMock(spec=Job)
    j.id = id
    j.title = title
    j.description = "Build things"
    j.job_profile = {"title": "SWE"}
    return j


def _make_batch(id=1, job_id=1, status="COMPLETED", total=3, processed=2, failed=1):
    from app.models.batch import ScreeningBatch
    b = MagicMock(spec=ScreeningBatch)
    b.id = id
    b.job_id = job_id
    b.status = status
    b.total_resumes = total
    b.processed = processed
    b.failed = failed
    return b


# -- test_results_pagination ----------------------------------------------------

@pytest.mark.asyncio
async def test_results_pagination(client: AsyncClient):
    from app.api import jobs
    from app.main import app as fastapi_app

    mock_db = AsyncMock()

    async def mock_get_db():
        yield mock_db

    fastapi_app.dependency_overrides[jobs.get_db] = mock_get_db

    sr = _make_screening_result(job_id=1, resume_id=1)

    job_exec = MagicMock()
    job_exec.scalar_one_or_none.return_value = _make_job(id=1)

    count_exec = MagicMock()
    count_exec.scalar_one.return_value = 1

    class MockRow:
        def __init__(self, resume, sr):
            self.Resume = resume
            self.ScreeningResult = sr
            self.candidate_name = "MockCandidate"
            
    from app.models.resume import Resume
    resume = Resume(id=1, job_id=1, status="READY")
    row = MockRow(resume, None)

    items_exec = MagicMock()
    items_exec.all.return_value = [row]

    mock_db.execute = AsyncMock(
        side_effect=[job_exec, count_exec, items_exec]
    )

    try:
        response = await client.get(
            "/jobs/1/results?page=1&page_size=10"
        )

        assert response.status_code == 200
        body = response.json()

        assert body["total"] == 1
        assert body["page"] == 1
        assert body["page_size"] == 10
        assert len(body["items"]) == 1
        assert body["items"][0]["score"] is None
        assert body["items"][0]["status"] == "READY"
    finally:
        fastapi_app.dependency_overrides.clear()


# -- test_results_filter_by_decision -------------------------------------------

@pytest.mark.asyncio
async def test_results_filter_by_decision(client: AsyncClient):
    response = await client.get("/jobs/9999/results?decision=SHORTLIST")
    # job 9999 does not exist -> 404
    assert response.status_code == 404


# -- test_results_filter_by_score ----------------------------------------------

@pytest.mark.asyncio
async def test_results_filter_by_score(client: AsyncClient):
    response = await client.get("/jobs/9999/results?min_score=80&max_score=100")
    assert response.status_code == 404


# -- test_results_sort_by_score ------------------------------------------------

@pytest.mark.asyncio
async def test_results_sort_by_score(client: AsyncClient):
    response = await client.get("/jobs/9999/results?sort_by=score")
    assert response.status_code == 404  # job doesn't exist, correct auth check


# -- test_candidate_detail -----------------------------------------------------

@pytest.mark.asyncio
async def test_candidate_detail(client: AsyncClient):
    response = await client.get("/jobs/9999/results/1")
    assert response.status_code == 404  # job 9999 doesn't exist


# -- test_candidate_detail_includes_summary_and_experience ---------------------

@pytest.mark.asyncio
async def test_candidate_detail_includes_summary_and_experience(client: AsyncClient):
    """CandidateProfileDetail must expose summary/total_experience_years (Candidate 360)."""
    from app.api import jobs
    from app.main import app as fastapi_app
    from app.models.profile import CandidateProfile

    mock_db = AsyncMock()

    async def mock_get_db():
        yield mock_db

    fastapi_app.dependency_overrides[jobs.get_db] = mock_get_db

    job_exec = MagicMock()
    job_exec.scalar_one_or_none.return_value = _make_job(id=1)

    resume_exec = MagicMock()
    resume_exec.scalar_one_or_none.return_value = _make_resume(id=1, job_id=1)

    profile = MagicMock(spec=CandidateProfile)
    profile.name = "Jane Doe"
    profile.email = "jane@example.com"
    profile.phone = "555-1234"
    profile.summary = "Senior backend engineer with distributed systems experience."
    profile.total_experience_years = 6.5
    profile.education = []
    profile.experience = []
    profile.skills = ["Python"]
    profile.projects = []
    profile.certifications = []
    profile.languages = []
    profile.achievements = []
    profile_exec = MagicMock()
    profile_exec.scalar_one_or_none.return_value = profile

    screening_exec = MagicMock()
    screening_exec.scalar_one_or_none.return_value = None

    interview_exec = MagicMock()
    interview_exec.scalar_one_or_none.return_value = None

    mock_db.execute = AsyncMock(
        side_effect=[job_exec, resume_exec, profile_exec, screening_exec, interview_exec]
    )

    try:
        response = await client.get("/jobs/1/results/1")
        assert response.status_code == 200
        body = response.json()
        assert body["profile"]["summary"] == "Senior backend engineer with distributed systems experience."
        assert body["profile"]["total_experience_years"] == 6.5
    finally:
        fastapi_app.dependency_overrides.clear()


# -- test_batch_progress -------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_progress(client: AsyncClient):
    response = await client.get("/jobs/9999/progress")
    assert response.status_code == 404  # job 9999 doesn't exist


# -- test_duplicate_screening_idempotent ---------------------------------------

@pytest.mark.asyncio
async def test_duplicate_screening_idempotent():
    """ScreenerService skips insertion when a result already exists."""

    from app.services.screener import screener_service
    from app.models.job import Job
    from app.services.embeddings import embedding_router
    from app.core.config import settings

    with patch(
        "app.services.screener.vector_store"
    ) as mock_vs, patch(
        "app.services.screener.ScreenerService.evaluate_candidate"
    ) as mock_eval, patch.object(
        embedding_router,
        "generate_embedding",
        new_callable=AsyncMock,
    ) as mock_embedding:

        from unittest.mock import MagicMock as _MM
        from app.services.model_registry import EmbeddingProfileConfig
        _mock_profile_cfg = _MM(spec=EmbeddingProfileConfig)
        _mock_profile_cfg.collection = "resumes"
        mock_embedding.return_value = (
            [0.1] * settings.EMBEDDING_DIMENSION,
            _mock_profile_cfg,
        )

        mock_vs.search = AsyncMock(
            return_value=[
                (
                    "1",
                    0.9,
                    {
                        "resume_id": 42,
                        "job_id": 1,
                        "profile": {
                            "skills": ["Python"]
                        },
                    },
                )
            ]
        )

        mock_eval.return_value = {
            "score": 88.0,
            "strengths": ["Python"],
            "gaps": [],
            "evidence": ["3yr"],
            "decision": "SHORTLIST",
        }

        mock_db = AsyncMock()

        # Existing ScreeningResult -> idempotency guard should skip insertion.
        existing_exec = MagicMock()
        existing_exec.scalar_one_or_none.return_value = MagicMock()

        count_exec = MagicMock()
        count_exec.scalar_one.return_value = 1

        # screen_job now also sources the adaptive-gate thresholds via
        # settings_service.get_effective_screening_config(db) (one extra
        # db.execute call, between the count query and the per-candidate
        # idempotency check) - no AppSettings row -> falls back to env defaults.
        settings_exec = MagicMock()
        settings_exec.scalar_one_or_none.return_value = None

        mock_db.execute = AsyncMock(
            side_effect=[count_exec, settings_exec, existing_exec]
        )
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()

        mock_job = MagicMock(spec=Job)
        mock_job.id = 1
        mock_job.job_profile = {
            "title": "Dev"
        }

        results = await screener_service.screen_job(
            mock_db,
            mock_job,
        )

        assert results == []

        mock_embedding.assert_called_once_with(
            "{'title': 'Dev'}",
            required_profile_name=ANY,
        )

        mock_vs.search.assert_called_once()

        search_kwargs = mock_vs.search.call_args.kwargs

        assert search_kwargs["query_filter"] == {
            "job_id": 1
        }

        mock_db.add.assert_not_called()
        mock_eval.assert_not_called()


# -- test_update_decision ------------------------------------------------------

@pytest.mark.asyncio
async def test_update_decision_valid(client: AsyncClient):
    from app.api import jobs
    from app.main import app as fastapi_app
    mock_db = AsyncMock()
    async def mock_get_db():
        yield mock_db
        
    fastapi_app.dependency_overrides[jobs.get_db] = mock_get_db
    
    mock_job_res = MagicMock()
    mock_job_res.scalar_one_or_none.return_value = _make_job(id=1)
    
    mock_resume_res = MagicMock()
    mock_resume_res.scalar_one_or_none.return_value = _make_resume(id=1, job_id=1)
    
    sr = _make_screening_result(job_id=1, resume_id=1, decision="REVIEW")
    mock_sr_res = MagicMock()
    mock_sr_res.scalar_one_or_none.return_value = sr
    
    mock_profile_res = MagicMock()
    mock_profile_res.scalar_one_or_none.return_value = None
    
    mock_db.execute.side_effect = [mock_job_res, mock_resume_res, mock_sr_res, mock_profile_res]
    
    response = await client.patch("/jobs/1/results/1/decision", json={"decision": "SHORTLIST"})
    assert response.status_code == 200
    assert response.json()["decision"] == "SHORTLIST"
    mock_db.commit.assert_called_once()
    
    fastapi_app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_update_decision_invalid(client: AsyncClient):
    response = await client.patch("/jobs/1/results/1/decision", json={"decision": "INVALID"})
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_update_decision_wrong_association(client: AsyncClient):
    from app.api import jobs
    from app.main import app as fastapi_app
    mock_db = AsyncMock()
    async def mock_get_db():
        yield mock_db
        
    fastapi_app.dependency_overrides[jobs.get_db] = mock_get_db
    
    mock_job_res = MagicMock()
    mock_job_res.scalar_one_or_none.return_value = _make_job(id=1)
    
    mock_resume_res = MagicMock()
    mock_resume_res.scalar_one_or_none.return_value = None
    
    mock_db.execute.side_effect = [mock_job_res, mock_resume_res]
    
    response = await client.patch("/jobs/1/results/1/decision", json={"decision": "SHORTLIST"})
    assert response.status_code == 404
    assert response.json()["detail"] == "Resume not found for this job"
    
    fastapi_app.dependency_overrides.clear()
