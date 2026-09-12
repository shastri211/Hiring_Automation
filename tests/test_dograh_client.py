import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from app.services.dograh import DograhClient


def _patched_settings(**overrides):
    """Context manager stack helper: patches app.core.config.settings attrs."""
    patchers = [patch(f"app.services.dograh.settings.{k}", v) for k, v in overrides.items()]
    return patchers


class _CtxStack:
    def __init__(self, patchers):
        self.patchers = patchers

    def __enter__(self):
        for p in self.patchers:
            p.start()
        return self

    def __exit__(self, *a):
        for p in self.patchers:
            p.stop()


def patched(**overrides):
    return _CtxStack(_patched_settings(**overrides))


# -- is_configured --------------------------------------------------------

def test_is_configured_true_when_all_three_set():
    with patched(
        DOGRAH_BASE_URL="https://dograh.example.com",
        DOGRAH_EMBED_TOKEN="tok",
        PUBLIC_APP_BASE_URL="https://app.example.com",
    ):
        assert DograhClient().is_configured is True


@pytest.mark.parametrize(
    "missing",
    ["DOGRAH_BASE_URL", "DOGRAH_EMBED_TOKEN", "PUBLIC_APP_BASE_URL"],
)
def test_is_configured_false_when_any_of_three_missing(missing):
    values = {
        "DOGRAH_BASE_URL": "https://dograh.example.com",
        "DOGRAH_EMBED_TOKEN": "tok",
        "PUBLIC_APP_BASE_URL": "https://app.example.com",
    }
    values[missing] = None
    with patched(**values):
        assert DograhClient().is_configured is False


def test_is_configured_ignores_api_key_and_workflow_id():
    """DOGRAH_API_KEY/DOGRAH_WORKFLOW_ID are only used by get_run/test_connection,
    not by link generation - is_configured must not require them."""
    with patched(
        DOGRAH_BASE_URL="https://dograh.example.com",
        DOGRAH_EMBED_TOKEN="tok",
        PUBLIC_APP_BASE_URL="https://app.example.com",
        DOGRAH_API_KEY=None,
        DOGRAH_WORKFLOW_ID=None,
    ):
        assert DograhClient().is_configured is True


# -- get_run ---------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_run_requires_config():
    with patched(DOGRAH_BASE_URL=None, DOGRAH_API_KEY=None):
        with pytest.raises(ValueError):
            await DograhClient().get_run("1", "2")


@pytest.mark.asyncio
async def test_get_run_request_shape_and_success():
    mock_response = MagicMock()
    mock_response.json.return_value = {"id": 42, "is_completed": True}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False

    with patched(DOGRAH_BASE_URL="https://dograh.example.com", DOGRAH_API_KEY="key123"):
        with patch("app.services.dograh.httpx.AsyncClient", return_value=mock_client):
            result = await DograhClient().get_run("7", "99")

    assert result == {"id": 42, "is_completed": True}
    args, kwargs = mock_client.get.call_args
    assert args[0] == "https://dograh.example.com/api/v1/workflow/7/runs/99"
    assert kwargs["headers"] == {"X-API-Key": "key123"}
    mock_response.raise_for_status.assert_called_once()


@pytest.mark.asyncio
async def test_get_run_propagates_http_error():
    import httpx

    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "error", request=MagicMock(), response=MagicMock(status_code=500)
    )

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False

    with patched(DOGRAH_BASE_URL="https://dograh.example.com", DOGRAH_API_KEY="key123"):
        with patch("app.services.dograh.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await DograhClient().get_run("7", "99")


# -- test_connection ---------------------------------------------------------

@pytest.mark.asyncio
async def test_test_connection_not_configured():
    with patched(DOGRAH_BASE_URL=None, DOGRAH_API_KEY=None, DOGRAH_WORKFLOW_ID=None):
        result = await DograhClient().test_connection()
    assert result["success"] is False


@pytest.mark.asyncio
async def test_test_connection_missing_workflow_id():
    with patched(DOGRAH_BASE_URL="https://dograh.example.com", DOGRAH_API_KEY="key", DOGRAH_WORKFLOW_ID=None):
        result = await DograhClient().test_connection()
    assert result["success"] is False
    assert "WORKFLOW_ID" in result["message"]


@pytest.mark.asyncio
async def test_test_connection_success():
    mock_response = MagicMock()
    mock_response.status_code = 200

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False

    with patched(
        DOGRAH_BASE_URL="https://dograh.example.com",
        DOGRAH_API_KEY="key123",
        DOGRAH_WORKFLOW_ID="7",
    ):
        with patch("app.services.dograh.httpx.AsyncClient", return_value=mock_client):
            result = await DograhClient().test_connection()

    assert result["success"] is True
    args, kwargs = mock_client.get.call_args
    assert args[0] == "https://dograh.example.com/api/v1/workflow/7/runs"
    assert kwargs["headers"] == {"X-API-Key": "key123"}
    assert kwargs["params"] == {"page": 1, "limit": 1}


@pytest.mark.asyncio
async def test_test_connection_unauthorized():
    mock_response = MagicMock()
    mock_response.status_code = 401

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False

    with patched(
        DOGRAH_BASE_URL="https://dograh.example.com",
        DOGRAH_API_KEY="badkey",
        DOGRAH_WORKFLOW_ID="7",
    ):
        with patch("app.services.dograh.httpx.AsyncClient", return_value=mock_client):
            result = await DograhClient().test_connection()

    assert result["success"] is False


@pytest.mark.asyncio
async def test_test_connection_network_error():
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=Exception("boom"))
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False

    with patched(
        DOGRAH_BASE_URL="https://dograh.example.com",
        DOGRAH_API_KEY="key123",
        DOGRAH_WORKFLOW_ID="7",
    ):
        with patch("app.services.dograh.httpx.AsyncClient", return_value=mock_client):
            result = await DograhClient().test_connection()

    assert result["success"] is False
    assert "reach" in result["message"].lower()
