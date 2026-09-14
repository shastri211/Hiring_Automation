import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check_reports_all_dependencies_ok(client: AsyncClient):
    """Confirms Qdrant is checked alongside Postgres/Redis - previously the
    health endpoint would report "ok" even if Qdrant was fully down."""
    with patch(
        "app.api.health.vector_store.client.get_collections", new_callable=AsyncMock
    ) as mock_qdrant, patch(
        "app.api.health.queue_service.redis_client.ping", new_callable=AsyncMock
    ) as mock_redis:
        mock_qdrant.return_value = []
        mock_redis.return_value = True

        response = await client.get("/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["db"] == "ok"
        assert body["redis"] == "ok"
        assert body["qdrant"] == "ok"


@pytest.mark.asyncio
async def test_health_check_reports_qdrant_down(client: AsyncClient):
    with patch(
        "app.api.health.vector_store.client.get_collections", new_callable=AsyncMock
    ) as mock_qdrant, patch(
        "app.api.health.queue_service.redis_client.ping", new_callable=AsyncMock
    ) as mock_redis:
        mock_qdrant.side_effect = Exception("connection refused")
        mock_redis.return_value = True

        response = await client.get("/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "error"
        assert body["qdrant"] == "error"
        assert body["db"] == "ok"
