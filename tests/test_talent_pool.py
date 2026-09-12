import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient


def _make_entry(id=1, resume_id=7, tags=None, notes=None, added_from_job_id=None):
    from app.models.talent_pool import TalentPoolEntry
    import datetime

    e = MagicMock(spec=TalentPoolEntry)
    e.id = id
    e.resume_id = resume_id
    e.added_from_job_id = added_from_job_id
    e.tags = tags or []
    e.notes = notes
    e.added_at = datetime.datetime.utcnow()
    e.updated_at = None
    return e


@pytest.mark.asyncio
async def test_add_to_talent_pool_creates_new_entry(client: AsyncClient):
    from app.api import talent_pool as talent_pool_api
    from app.main import app as fastapi_app

    mock_db = AsyncMock()

    async def mock_get_db():
        yield mock_db

    fastapi_app.dependency_overrides[talent_pool_api.get_db] = mock_get_db

    missing_exec = MagicMock()
    missing_exec.scalar_one_or_none.return_value = None

    summary_exec = MagicMock()
    summary_exec.all.return_value = []

    mock_db.execute = AsyncMock(side_effect=[missing_exec, summary_exec])
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    async def _refresh(obj):
        obj.id = 1
        obj.added_at = None
        obj.updated_at = None

    mock_db.refresh = AsyncMock(side_effect=_refresh)

    try:
        response = await client.post(
            "/talent-pool/", json={"resume_id": 7, "tags": ["python", "senior"]}
        )
        assert response.status_code == 201
        body = response.json()
        assert body["resume_id"] == 7
        assert set(body["tags"]) == {"python", "senior"}
        mock_db.add.assert_called_once()
    finally:
        fastapi_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_add_to_talent_pool_merges_tags_on_repeat_add(client: AsyncClient):
    """Idempotent upsert: repeat-add merges tags, never 409."""
    from app.api import talent_pool as talent_pool_api
    from app.main import app as fastapi_app

    mock_db = AsyncMock()

    async def mock_get_db():
        yield mock_db

    fastapi_app.dependency_overrides[talent_pool_api.get_db] = mock_get_db

    existing = _make_entry(id=5, resume_id=7, tags=["python"])
    existing_exec = MagicMock()
    existing_exec.scalar_one_or_none.return_value = existing

    summary_exec = MagicMock()
    summary_exec.all.return_value = []

    mock_db.execute = AsyncMock(side_effect=[existing_exec, summary_exec])
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    try:
        response = await client.post(
            "/talent-pool/", json={"resume_id": 7, "tags": ["senior"]}
        )
        assert response.status_code == 201
        body = response.json()
        assert set(body["tags"]) == {"python", "senior"}
    finally:
        fastapi_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_talent_pool_paginated(client: AsyncClient):
    from app.api import talent_pool as talent_pool_api
    from app.main import app as fastapi_app

    mock_db = AsyncMock()

    async def mock_get_db():
        yield mock_db

    fastapi_app.dependency_overrides[talent_pool_api.get_db] = mock_get_db

    count_exec = MagicMock()
    count_exec.scalar_one.return_value = 1

    entry = _make_entry(id=1, resume_id=7, tags=["python"])
    rows_exec = MagicMock()
    rows_exec.scalars.return_value.all.return_value = [entry]

    summary_exec = MagicMock()
    summary_exec.all.return_value = []

    mock_db.execute = AsyncMock(side_effect=[count_exec, rows_exec, summary_exec])

    try:
        response = await client.get("/talent-pool/?tag=python")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert len(body["items"]) == 1
        assert body["items"][0]["resume_id"] == 7
    finally:
        fastapi_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_update_talent_pool_entry_not_found(client: AsyncClient):
    from app.api import talent_pool as talent_pool_api
    from app.main import app as fastapi_app

    mock_db = AsyncMock()

    async def mock_get_db():
        yield mock_db

    fastapi_app.dependency_overrides[talent_pool_api.get_db] = mock_get_db

    missing_exec = MagicMock()
    missing_exec.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=missing_exec)

    try:
        response = await client.patch("/talent-pool/999", json={"notes": "hello"})
        assert response.status_code == 404
    finally:
        fastapi_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_talent_pool_entry(client: AsyncClient):
    from app.api import talent_pool as talent_pool_api
    from app.main import app as fastapi_app

    mock_db = AsyncMock()

    async def mock_get_db():
        yield mock_db

    fastapi_app.dependency_overrides[talent_pool_api.get_db] = mock_get_db

    entry = _make_entry(id=1, resume_id=7)
    found_exec = MagicMock()
    found_exec.scalar_one_or_none.return_value = entry

    mock_db.execute = AsyncMock(return_value=found_exec)
    mock_db.delete = AsyncMock()
    mock_db.commit = AsyncMock()

    try:
        response = await client.delete("/talent-pool/1")
        assert response.status_code == 204
        mock_db.delete.assert_called_once_with(entry)
    finally:
        fastapi_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_talent_pool_entry_not_found(client: AsyncClient):
    from app.api import talent_pool as talent_pool_api
    from app.main import app as fastapi_app

    mock_db = AsyncMock()

    async def mock_get_db():
        yield mock_db

    fastapi_app.dependency_overrides[talent_pool_api.get_db] = mock_get_db

    missing_exec = MagicMock()
    missing_exec.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=missing_exec)

    try:
        response = await client.delete("/talent-pool/999")
        assert response.status_code == 404
    finally:
        fastapi_app.dependency_overrides.clear()
