import pytest
from collections import namedtuple
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient

from app.services.interview_analysis import parse_evaluation_envelope

_Row = namedtuple("Row", ["interview", "job_title", "candidate_name"])


def _make_interview(id=1, job_id=1, resume_id=1, status="COMPLETED", evaluation=None):
    from app.models.interview import Interview
    import datetime

    i = MagicMock(spec=Interview)
    i.id = id
    i.job_id = job_id
    i.resume_id = resume_id
    i.status = status
    i.evaluation = evaluation
    i.created_at = datetime.datetime.utcnow()
    return i


# -- parse_evaluation_envelope (defensive parsing) ------------------------------

def test_parse_envelope_canonical_shape():
    envelope = {
        "source": "dograh",
        "workflow_run_id": "run-123",
        "call_disposition": "interested",
        "gathered_context": {"foo": "bar"},
        "cost_info": {"call_duration_seconds": 120},
        "user_recording_url": "https://example.com/user.mp3",
        "bot_recording_url": "https://example.com/bot.mp3",
    }
    parsed = parse_evaluation_envelope(envelope)
    assert parsed["source"] == "dograh"
    assert parsed["call_disposition"] == "interested"
    assert parsed["cost_info"]["call_duration_seconds"] == 120


def test_parse_envelope_legacy_malformed_dict_buckets_unspecified():
    parsed = parse_evaluation_envelope({"some_other_legacy_key": "value"})
    assert parsed["source"] == "unspecified"
    assert parsed["call_disposition"] == "unspecified"
    assert parsed["gathered_context"] == {}
    assert parsed["cost_info"] == {}


def test_parse_envelope_non_dict_never_raises():
    assert parse_evaluation_envelope(None)["call_disposition"] == "unspecified"
    assert parse_evaluation_envelope("a plain string")["call_disposition"] == "unspecified"
    assert parse_evaluation_envelope([1, 2, 3])["call_disposition"] == "unspecified"
    assert parse_evaluation_envelope(42)["call_disposition"] == "unspecified"


# -- summary endpoint ------------------------------------------------------------

@pytest.mark.asyncio
async def test_interview_analysis_summary(client: AsyncClient):
    from app.api import interview_analysis as ia_api
    from app.main import app as fastapi_app

    mock_db = AsyncMock()

    async def mock_get_db():
        yield mock_db

    fastapi_app.dependency_overrides[ia_api.get_db] = mock_get_db

    interviews = [
        _make_interview(
            id=1,
            status="COMPLETED",
            evaluation={
                "source": "dograh",
                "call_disposition": "interested",
                "cost_info": {"call_duration_seconds": 100},
            },
        ),
        _make_interview(id=2, status="SCHEDULED", evaluation=None),
        _make_interview(id=3, status="COMPLETED", evaluation={"legacy": True}),
    ]

    exec_result = MagicMock()
    exec_result.scalars.return_value.all.return_value = interviews
    mock_db.execute = AsyncMock(return_value=exec_result)

    try:
        response = await client.get("/interview-analysis/summary")
        assert response.status_code == 200
        body = response.json()
        assert body["total_interviews"] == 3
        assert body["completed_interviews"] == 2
        assert body["disposition_breakdown"]["interested"] == 1
        assert body["disposition_breakdown"]["unspecified"] == 2
        assert body["avg_call_duration_seconds"] == 100
    finally:
        fastapi_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_interview_analysis_summary_empty(client: AsyncClient):
    from app.api import interview_analysis as ia_api
    from app.main import app as fastapi_app

    mock_db = AsyncMock()

    async def mock_get_db():
        yield mock_db

    fastapi_app.dependency_overrides[ia_api.get_db] = mock_get_db

    exec_result = MagicMock()
    exec_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=exec_result)

    try:
        response = await client.get("/interview-analysis/summary")
        assert response.status_code == 200
        body = response.json()
        assert body["total_interviews"] == 0
        assert body["completion_rate"] == 0.0
        assert body["avg_call_duration_seconds"] is None
    finally:
        fastapi_app.dependency_overrides.clear()


# -- list endpoint ----------------------------------------------------------------

@pytest.mark.asyncio
async def test_interview_analysis_list_paginated(client: AsyncClient):
    from app.api import interview_analysis as ia_api
    from app.main import app as fastapi_app

    mock_db = AsyncMock()

    async def mock_get_db():
        yield mock_db

    fastapi_app.dependency_overrides[ia_api.get_db] = mock_get_db

    interview = _make_interview(
        id=1,
        status="COMPLETED",
        evaluation={"source": "dograh", "call_disposition": "interested"},
    )
    row = _Row(interview, "Backend Engineer", "Jane Doe")

    count_exec = MagicMock()
    count_exec.scalar_one.return_value = 1

    rows_exec = MagicMock()
    rows_exec.all.return_value = [row]

    mock_db.execute = AsyncMock(side_effect=[count_exec, rows_exec])

    try:
        response = await client.get("/interview-analysis/")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["call_disposition"] == "interested"
        assert body["items"][0]["job_title"] == "Backend Engineer"
    finally:
        fastapi_app.dependency_overrides.clear()
