import pytest
from collections import namedtuple
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient

# Supports both positional indexing (row[0]) and attribute access (row.job_title),
# matching how a real SQLAlchemy Row behaves for `select(Interview, Job.title.label(...), ...)`.
_Row = namedtuple("Row", ["interview", "job_title", "candidate_name", "resume_filename"])


def _make_interview(id=1, job_id=1, resume_id=1, status="SCHEDULED"):
    from app.models.interview import Interview
    import datetime

    i = MagicMock(spec=Interview)
    i.id = id
    i.job_id = job_id
    i.resume_id = resume_id
    i.status = status
    i.transcript = None
    i.evaluation = None
    i.created_at = datetime.datetime.utcnow()
    i.updated_at = None
    return i


@pytest.mark.asyncio
async def test_get_global_interviews_paginated(client: AsyncClient):
    from app.api import interviews as interviews_api
    from app.main import app as fastapi_app

    mock_db = AsyncMock()

    async def mock_get_db():
        yield mock_db

    fastapi_app.dependency_overrides[interviews_api.get_db] = mock_get_db

    count_exec = MagicMock()
    count_exec.scalar_one.return_value = 1

    interview = _make_interview(id=1, job_id=1, resume_id=1, status="SCHEDULED")
    row = _Row(interview, "Backend Engineer", "Jane Doe", "jane.pdf")
    rows_exec = MagicMock()
    rows_exec.all.return_value = [row]

    mock_db.execute = AsyncMock(side_effect=[count_exec, rows_exec])

    try:
        response = await client.get("/interviews/?status=scheduled")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["job_title"] == "Backend Engineer"
        assert body["items"][0]["candidate_name"] == "Jane Doe"
        assert body["items"][0]["status"] == "SCHEDULED"
    finally:
        fastapi_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_global_interviews_filters_by_job_id(client: AsyncClient):
    from app.api import interviews as interviews_api
    from app.main import app as fastapi_app

    mock_db = AsyncMock()

    async def mock_get_db():
        yield mock_db

    fastapi_app.dependency_overrides[interviews_api.get_db] = mock_get_db

    count_exec = MagicMock()
    count_exec.scalar_one.return_value = 0

    rows_exec = MagicMock()
    rows_exec.all.return_value = []

    mock_db.execute = AsyncMock(side_effect=[count_exec, rows_exec])

    try:
        response = await client.get("/interviews/?job_id=999")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 0
        assert body["items"] == []
    finally:
        fastapi_app.dependency_overrides.clear()
