import pytest
from unittest.mock import patch, MagicMock
from app.services.embeddings import embedding_router, EmbeddingRouter, EmbeddingError
from app.services.model_registry import model_registry, EmbeddingProfileConfig

@pytest.fixture(autouse=True)
def reset_cooldowns():
    model_registry._embedding_cooldowns.clear()
    yield
    model_registry._embedding_cooldowns.clear()

@pytest.mark.asyncio
async def test_generate_embedding_local_fallback():
    with patch("app.services.model_registry.ModelRegistry.get_eligible_embedding_profiles") as mock_get_profiles:
        mock_get_profiles.return_value = [
            EmbeddingProfileConfig(
                provider="local",
                model="all-MiniLM-L6-v2",
                dimensions=384,
                metric="Cosine",
                collection="test",
                task_profile="RETRIEVAL_DOCUMENT"
            )
        ]
        
        router = EmbeddingRouter()
        
        # Mock the local embedder to return a 384-d vector
        mock_local = MagicMock()
        mock_local.encode.return_value = [0.1] * 384
        
        with patch.object(router, '_get_local_model', return_value=mock_local):
            vec, profile = await router.generate_embedding("test")
            assert len(vec) == 384
            assert vec == [0.1] * 384
            assert profile.provider == "local"

@pytest.mark.asyncio
async def test_generate_embedding_success():
    with patch("app.services.model_registry.ModelRegistry.get_eligible_embedding_profiles") as mock_get_profiles:
        mock_get_profiles.return_value = [
            EmbeddingProfileConfig(
                provider="gemini",
                model="models/text-embedding-004",
                dimensions=768,
                metric="Cosine",
                collection="test",
                task_profile="RETRIEVAL_DOCUMENT"
            )
        ]
        with patch('app.services.embeddings.genai.Client') as MockClient:
            mock_client = MockClient.return_value
            mock_response = MagicMock()
            mock_emb = MagicMock()
            mock_emb.values = [0.1] * 768
            mock_response.embeddings = [mock_emb]
            mock_client.models.embed_content.return_value = mock_response
            
            with patch('app.services.embeddings.settings.GEMINI_API_KEY', 'dummy_key'):
                router = EmbeddingRouter()
                vec, profile = await router.generate_embedding("test text")
                
                assert len(vec) == 768
                assert profile.provider == "gemini"
                mock_client.models.embed_content.assert_called_once()
