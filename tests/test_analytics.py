import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_funnel_endpoint(client: AsyncClient):
    from app.api import analytics as analytics_api
    from app.main import app as fastapi_app

    mock_db = AsyncMock()

    async def mock_get_db():
        yield mock_db

    fastapi_app.dependency_overrides[analytics_api.get_db] = mock_get_db

    row = MagicMock()
    row.uploaded = 10
    row.processed = 8
    row.screened = 6
    row.shortlisted = 3
    row.interviewed = 2
    row.completed = 1

    exec_result = MagicMock()
    exec_result.one.return_value = row
    mock_db.execute = AsyncMock(return_value=exec_result)

    try:
        response = await client.get("/analytics/funnel?job_id=1")
        assert response.status_code == 200
        body = response.json()
        assert body == {
            "job_id": 1,
            "uploaded": 10,
            "processed": 8,
            "screened": 6,
            "shortlisted": 3,
            "interviewed": 2,
            "completed": 1,
        }
    finally:
        fastapi_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_decisions_endpoint(client: AsyncClient):
    from app.api import analytics as analytics_api
    from app.main import app as fastapi_app

    mock_db = AsyncMock()

    async def mock_get_db():
        yield mock_db

    fastapi_app.dependency_overrides[analytics_api.get_db] = mock_get_db

    exec_result = MagicMock()
    exec_result.all.return_value = [("SHORTLIST", 3), ("REJECT", 5), (None, 2)]
    mock_db.execute = AsyncMock(return_value=exec_result)

    try:
        response = await client.get("/analytics/decisions")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 10
        assert {"decision": "SHORTLIST", "count": 3} in body["items"]
    finally:
        fastapi_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_throughput_endpoint_zero_fills_days(client: AsyncClient):
    from app.api import analytics as analytics_api
    from app.main import app as fastapi_app

    mock_db = AsyncMock()

    async def mock_get_db():
        yield mock_db

    fastapi_app.dependency_overrides[analytics_api.get_db] = mock_get_db

    exec_result = MagicMock()
    exec_result.all.return_value = []  # no data at all
    mock_db.execute = AsyncMock(return_value=exec_result)

    try:
        response = await client.get("/analytics/throughput?days=7")
        assert response.status_code == 200
        body = response.json()
        assert len(body["items"]) == 7
        assert all(item["count"] == 0 for item in body["items"])
    finally:
        fastapi_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_time_in_stage_endpoint_handles_no_data(client: AsyncClient):
    from app.api import analytics as analytics_api
    from app.main import app as fastapi_app

    mock_db = AsyncMock()

    async def mock_get_db():
        yield mock_db

    fastapi_app.dependency_overrides[analytics_api.get_db] = mock_get_db

    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=exec_result)

    try:
        response = await client.get("/analytics/time-in-stage")
        assert response.status_code == 200
        body = response.json()
        assert body["resume_to_screened_seconds_approx"] is None
        assert body["screened_to_interview_seconds_approx"] is None
    finally:
        fastapi_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_job_volume_endpoint(client: AsyncClient):
    from app.api import analytics as analytics_api
    from app.main import app as fastapi_app

    mock_db = AsyncMock()

    async def mock_get_db():
        yield mock_db

    fastapi_app.dependency_overrides[analytics_api.get_db] = mock_get_db

    exec_result = MagicMock()
    exec_result.all.return_value = [(1, "Backend Engineer", 12), (2, "Data Scientist", 4)]
    mock_db.execute = AsyncMock(return_value=exec_result)

    try:
        response = await client.get("/analytics/job-volume")
        assert response.status_code == 200
        body = response.json()
        assert body["items"] == [
            {"job_id": 1, "job_title": "Backend Engineer", "resume_count": 12},
            {"job_id": 2, "job_title": "Data Scientist", "resume_count": 4},
        ]
    finally:
        fastapi_app.dependency_overrides.clear()
