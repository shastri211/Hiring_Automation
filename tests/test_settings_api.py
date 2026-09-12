import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient


def _make_app_settings(**overrides):
    from app.models.settings import AppSettings
    import datetime

    s = MagicMock(spec=AppSettings)
    s.id = 1
    s.org_name = None
    s.min_candidates_to_screen = None
    s.max_candidates_to_screen = None
    s.semantic_gap_threshold = None
    s.auto_email_on_shortlist = False
    s.shortlist_email_template_id = None
    s.auto_email_on_interview_scheduled = False
    s.interview_scheduled_email_template_id = None
    s.created_at = datetime.datetime.utcnow()
    s.updated_at = None
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


@pytest.mark.asyncio
async def test_get_settings_creates_singleton_when_missing(client: AsyncClient):
    from app.api import settings as settings_api
    from app.main import app as fastapi_app

    mock_db = AsyncMock()

    async def mock_get_db():
        yield mock_db

    fastapi_app.dependency_overrides[settings_api.get_db] = mock_get_db

    missing_exec = MagicMock()
    missing_exec.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=missing_exec)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    async def _refresh(obj):
        # Simulate the DB populating server-side column defaults after insert,
        # matching what a real `db.refresh()` (SELECT-reload) would do.
        import datetime
        obj.id = 1
        obj.org_name = None
        obj.min_candidates_to_screen = None
        obj.max_candidates_to_screen = None
        obj.semantic_gap_threshold = None
        obj.auto_email_on_shortlist = False
        obj.shortlist_email_template_id = None
        obj.auto_email_on_interview_scheduled = False
        obj.interview_scheduled_email_template_id = None
        obj.created_at = datetime.datetime.utcnow()
        obj.updated_at = None

    mock_db.refresh = AsyncMock(side_effect=_refresh)

    try:
        response = await client.get("/settings/")
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == 1
        assert body["auto_email_on_shortlist"] is False
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
    finally:
        fastapi_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_patch_settings_rejects_unknown_template_id(client: AsyncClient):
    from app.api import settings as settings_api
    from app.main import app as fastapi_app

    mock_db = AsyncMock()

    async def mock_get_db():
        yield mock_db

    fastapi_app.dependency_overrides[settings_api.get_db] = mock_get_db

    existing = _make_app_settings()
    settings_exec = MagicMock()
    settings_exec.scalar_one_or_none.return_value = existing

    template_exec = MagicMock()
    template_exec.scalar_one_or_none.return_value = None  # template does not exist

    mock_db.execute = AsyncMock(side_effect=[settings_exec, template_exec])

    try:
        response = await client.patch("/settings/", json={"shortlist_email_template_id": 999})
        assert response.status_code == 400
    finally:
        fastapi_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_patch_settings_updates_fields(client: AsyncClient):
    from app.api import settings as settings_api
    from app.main import app as fastapi_app

    mock_db = AsyncMock()

    async def mock_get_db():
        yield mock_db

    fastapi_app.dependency_overrides[settings_api.get_db] = mock_get_db

    existing = _make_app_settings()
    settings_exec = MagicMock()
    settings_exec.scalar_one_or_none.return_value = existing

    mock_db.execute = AsyncMock(return_value=settings_exec)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    try:
        response = await client.patch("/settings/", json={"org_name": "Acme Corp", "auto_email_on_shortlist": True})
        assert response.status_code == 200
        body = response.json()
        assert body["org_name"] == "Acme Corp"
        assert body["auto_email_on_shortlist"] is True
    finally:
        fastapi_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_effective_screening_config_falls_back_to_env_defaults():
    """No AppSettings row (or all-NULL fields) -> falls back individually to
    app.core.config.settings thresholds. This is the exact behavior
    app/services/screener.py::screen_job now relies on."""
    from app.services.settings import settings_service
    from app.core.config import settings as app_config

    mock_db = AsyncMock()
    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=exec_result)

    min_keep, max_keep, gap_threshold = await settings_service.get_effective_screening_config(mock_db)

    assert min_keep == app_config.MIN_CANDIDATES_TO_SCREEN
    assert max_keep == app_config.MAX_CANDIDATES_TO_SCREEN
    assert gap_threshold == app_config.SEMANTIC_GAP_THRESHOLD


@pytest.mark.asyncio
async def test_get_effective_screening_config_uses_db_overrides_when_set():
    from app.services.settings import settings_service

    mock_db = AsyncMock()
    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = _make_app_settings(
        min_candidates_to_screen=3, max_candidates_to_screen=15, semantic_gap_threshold=0.2
    )
    mock_db.execute = AsyncMock(return_value=exec_result)

    min_keep, max_keep, gap_threshold = await settings_service.get_effective_screening_config(mock_db)

    assert (min_keep, max_keep, gap_threshold) == (3, 15, 0.2)


@pytest.mark.asyncio
async def test_real_settings_round_trip(client: AsyncClient):
    """Real-DB smoke test proving the migration-backed table + get-or-create
    singleton actually works end to end."""
    try:
        response = await client.get("/settings/")
        assert response.status_code == 200
        assert response.json()["id"] == 1

        patch_response = await client.patch("/settings/", json={"org_name": "Real DB Test Org"})
        assert patch_response.status_code == 200
        assert patch_response.json()["org_name"] == "Real DB Test Org"

        get_response = await client.get("/settings/")
        assert get_response.json()["org_name"] == "Real DB Test Org"
    finally:
        # Reset so repeated local/dev runs against the same DB stay clean.
        await client.patch("/settings/", json={"org_name": None})
