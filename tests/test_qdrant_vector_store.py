import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.vector_store import QdrantVectorStore
from qdrant_client.models import PointStruct
from app.core.config import settings


@pytest.mark.asyncio
async def test_qdrant_create_collection():
    with patch('app.services.vector_store.AsyncQdrantClient') as MockClient:
        mock_instance = MockClient.return_value
        # Mock get_collections to return empty
        mock_collections = MagicMock()
        mock_collections.collections = []
        mock_instance.get_collections = AsyncMock(return_value=mock_collections)
        mock_instance.create_collection = AsyncMock()
        
        store = QdrantVectorStore()
        await store.create_collection("test_col")
        
        mock_instance.create_collection.assert_called_once()
        
@pytest.mark.asyncio
async def test_qdrant_add_points():
    with patch('app.services.vector_store.AsyncQdrantClient') as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.upsert = AsyncMock()
        
        store = QdrantVectorStore()
        test_vector = [0.1] * settings.EMBEDDING_DIMENSION
        await store.add_points(
            "test_col",
            ["123"],
            [test_vector],
            [{"key": "val"}],
        )
        mock_instance.upsert.assert_called_once()
        kwargs = mock_instance.upsert.call_args.kwargs
        assert kwargs["collection_name"] == "test_col"
        assert len(kwargs["points"]) == 1
        assert kwargs["points"][0].id == "123"
        assert kwargs["points"][0].vector == test_vector
        assert kwargs["points"][0].payload == {"key": "val"}

@pytest.mark.asyncio
async def test_qdrant_search():
    with patch('app.services.vector_store.AsyncQdrantClient') as MockClient:
        mock_instance = MockClient.return_value
        mock_result = MagicMock()
        mock_result.id = "123"
        mock_result.score = 0.95
        mock_result.payload = {"profile": "data"}
        mock_response = MagicMock()
        mock_response.points = [mock_result]
        mock_instance.query_points = AsyncMock(return_value=mock_response)
        
        store = QdrantVectorStore()
        test_vector = [0.1] * settings.EMBEDDING_DIMENSION

        results = await store.search("test_col", test_vector, 5)
        
        mock_instance.query_points.assert_called_once()
        assert len(results) == 1
        assert results[0][0] == "123"
        assert results[0][1] == 0.95
        assert results[0][2] == {"profile": "data"}
