import pytest
from contextlib import asynccontextmanager
from unittest.mock import patch, MagicMock, AsyncMock, ANY

from app.models.job import Job
from app.services.screener import screener_service
from app.services.embeddings import embedding_router
from app.core.config import settings


@asynccontextmanager
async def _fake_savepoint():
    """Stand-in for AsyncSession.begin_nested() - screen_job wraps each
    candidate's write in one so an IntegrityError on that candidate can't
    roll back everything already flushed earlier in the same call."""
    yield


def _mock_db_with_savepoints() -> AsyncMock:
    mock_db = AsyncMock()
    mock_db.begin_nested = MagicMock(side_effect=lambda: _fake_savepoint())
    return mock_db


@pytest.mark.asyncio
async def test_screen_job_success():
    with patch(
        "app.services.screener.vector_store"
    ) as mock_vs, patch(
        "app.services.screener.ScreenerService.evaluate_candidate"
    ) as mock_eval, patch.object(
        embedding_router,
        "generate_embedding",
        new_callable=AsyncMock,
    ) as mock_embedding:

        mock_profile = MagicMock()
        mock_profile.collection = settings.QDRANT_COLLECTION
        mock_embedding.return_value = (
            [0.1] * settings.EMBEDDING_DIMENSION,
            mock_profile
        )

        mock_vs.search = AsyncMock(
            return_value=[
                (
                    "123",
                    0.9,
                    {
                        "resume_id": 1,
                        "job_id": 10,
                        "profile": {
                            "skills": ["Python"]
                        },
                    },
                )
            ]
        )

        mock_eval.return_value = {
            "score": 85.5,
            "strengths": ["Python"],
            "gaps": [],
            "evidence": ["Has Python"],
            "decision": "SHORTLIST",
        }

        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = None
        exec_result.scalar_one.return_value = 1

        mock_db = _mock_db_with_savepoints()
        mock_db.execute = AsyncMock(return_value=exec_result)
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()

        mock_job = MagicMock(spec=Job)
        mock_job.id = 10
        mock_job.job_profile = {"title": "Dev"}

        results = await screener_service.screen_job(
            mock_db,
            mock_job,
        )

        mock_embedding.assert_called_once_with(
            "{'title': 'Dev'}",
            required_profile_name=ANY,
        )

        mock_vs.search.assert_called_once()

        search_kwargs = mock_vs.search.call_args.kwargs

        assert search_kwargs["collection_name"] == settings.QDRANT_COLLECTION
        assert search_kwargs["query_vector"] == [0.1] * settings.EMBEDDING_DIMENSION
        # limit depends on Phase 12 changes; it's MIN_CANDIDATES_TO_SCREEN internally but let's see what happens.
        assert search_kwargs["query_filter"] == {
            "job_id": 10
        }

        assert len(results) == 1
        assert results[0].score == 85.5
        assert results[0].decision == "SHORTLIST"
        assert results[0].resume_id == 1
        assert results[0].job_id == 10

        mock_eval.assert_called_once_with(
            {"title": "Dev"},
            {
                "skills": ["Python"]
            },
        )


@pytest.mark.asyncio
async def test_screen_job_no_profile():
    mock_db = AsyncMock()

    mock_job = MagicMock(spec=Job)
    mock_job.id = 10
    mock_job.job_profile = None

    with pytest.raises(
        ValueError,
        match="Job has no structured profile",
    ):
        await screener_service.screen_job(
            mock_db,
            mock_job,
        )


@pytest.mark.asyncio
async def test_screen_job_provider_failure():
    with patch("app.services.screener.vector_store") as mock_vs, \
         patch("app.services.screener.ScreenerService.evaluate_candidate") as mock_eval, \
         patch.object(embedding_router, "generate_embedding", new_callable=AsyncMock) as mock_embedding, \
         patch("app.services.screener._adaptive_pre_screen", return_value=[("123", 0.9, {})]):

        mock_profile = MagicMock()
        mock_profile.collection = settings.QDRANT_COLLECTION
        mock_embedding.return_value = ([0.1] * settings.EMBEDDING_DIMENSION, mock_profile)

        mock_vs.search = AsyncMock(
            return_value=[
                ("123", 0.9, {"resume_id": 1, "job_id": 10, "profile": {}})
            ]
        )

        mock_eval.side_effect = Exception("LLM Provider failed")

        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = None
        exec_result.scalar_one.return_value = 1 

        mock_db = _mock_db_with_savepoints()
        mock_db.execute = AsyncMock(return_value=exec_result)

        mock_job = MagicMock(spec=Job)
        mock_job.id = 10
        mock_job.job_profile = {"title": "Dev"}

        results = await screener_service.screen_job(mock_db, mock_job)

        assert len(results) == 1
        assert results[0].decision == "REVIEW"
        assert results[0].score is None
        assert "LLM Provider failed" in results[0].notes


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_score", ["not-a-number", 150, -5, True, None])
async def test_evaluate_candidate_rejects_invalid_score(bad_score):
    """A non-numeric or out-of-range score from the LLM must be rejected
    with a clear InvalidEvaluationResultError rather than reaching the DB
    column as-is and failing later as an opaque DataError."""
    from app.services.llm_provider import LLMProviderFactory, InvalidEvaluationResultError

    with patch.object(
        LLMProviderFactory, "generate_with_fallback", new_callable=AsyncMock
    ) as mock_generate:
        mock_generate.return_value = {"score": bad_score, "decision": "REVIEW"}

        with pytest.raises(InvalidEvaluationResultError):
            await screener_service.evaluate_candidate({"title": "Dev"}, {"skills": []})


@pytest.mark.asyncio
async def test_screen_job_one_candidates_db_failure_does_not_drop_others():
    """One candidate hitting an IntegrityError on flush must only unwind its
    own SAVEPOINT, not every ScreeningResult already flushed earlier in this
    same screen_job call (screen_job commits once at the very end)."""
    from sqlalchemy.exc import IntegrityError

    with patch("app.services.screener.vector_store") as mock_vs, \
         patch("app.services.screener.ScreenerService.evaluate_candidate") as mock_eval, \
         patch.object(embedding_router, "generate_embedding", new_callable=AsyncMock) as mock_embedding, \
         patch("app.services.screener._adaptive_pre_screen", side_effect=lambda cands, **kw: cands):

        mock_profile = MagicMock()
        mock_profile.collection = settings.QDRANT_COLLECTION
        mock_embedding.return_value = ([0.1] * settings.EMBEDDING_DIMENSION, mock_profile)

        mock_vs.search = AsyncMock(
            return_value=[
                ("1", 0.9, {"resume_id": 1, "job_id": 10, "profile": {}}),
                ("2", 0.8, {"resume_id": 2, "job_id": 10, "profile": {}}),
            ]
        )

        mock_eval.return_value = {
            "score": 80.0,
            "strengths": [],
            "gaps": [],
            "evidence": [],
            "decision": "SHORTLIST",
        }

        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = None
        exec_result.scalar_one.return_value = 2

        mock_db = _mock_db_with_savepoints()
        mock_db.execute = AsyncMock(return_value=exec_result)
        # First candidate's flush hits a duplicate-insert race; the second
        # must still succeed and be committed.
        mock_db.flush = AsyncMock(side_effect=[IntegrityError("dup", None, None), None])

        mock_job = MagicMock(spec=Job)
        mock_job.id = 10
        mock_job.job_profile = {"title": "Dev"}

        results = await screener_service.screen_job(mock_db, mock_job)

        assert len(results) == 1
        assert results[0].resume_id == 2
        mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_screen_job_exceeds_limit():
    with patch("app.services.screener.vector_store") as mock_vs, \
         patch("app.services.screener.ScreenerService.evaluate_candidate") as mock_eval, \
         patch.object(embedding_router, "generate_embedding", new_callable=AsyncMock) as mock_embedding:

        mock_profile = MagicMock()
        mock_profile.collection = settings.QDRANT_COLLECTION
        mock_embedding.return_value = ([0.1] * settings.EMBEDDING_DIMENSION, mock_profile)

        mock_vs.search = AsyncMock(return_value=[])

        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = None
        exec_result.scalar_one.return_value = 60

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=exec_result)

        mock_job = MagicMock(spec=Job)
        mock_job.id = 10
        mock_job.job_profile = {"title": "Dev"}

        await screener_service.screen_job(mock_db, mock_job)

        search_kwargs = mock_vs.search.call_args.kwargs
        assert search_kwargs["limit"] == 60