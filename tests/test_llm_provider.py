import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.services.llm_provider import LLMProviderFactory, BaseProvider, RateLimitError, LLMError, LLMExhaustionError
from app.services.model_registry import model_registry, LLMModelConfig

class SuccessProvider(BaseProvider):
    provider_name = "test_success"
    async def generate_json(self, model_name: str, prompt: str, schema: dict) -> dict:
        return {"result": "success"}

class RateLimitProvider(BaseProvider):
    provider_name = "test_ratelimit"
    async def generate_json(self, model_name: str, prompt: str, schema: dict) -> dict:
        raise RateLimitError("Rate limit exceeded")

class ServerErrorProvider(BaseProvider):
    provider_name = "test_5xx"
    async def generate_json(self, model_name: str, prompt: str, schema: dict) -> dict:
        raise LLMError("Transient 503 Service Unavailable")

class TimeoutProvider(BaseProvider):
    provider_name = "test_timeout"
    async def generate_json(self, model_name: str, prompt: str, schema: dict) -> dict:
        raise LLMError("Timeout")

class MalformedProvider(BaseProvider):
    provider_name = "test_malformed"
    async def generate_json(self, model_name: str, prompt: str, schema: dict) -> dict:
        raise LLMError("JSON decode error")

@pytest.fixture(autouse=True)
def reset_registry():
    model_registry._llm_cooldowns.clear()
    yield
    model_registry._llm_cooldowns.clear()

@pytest.mark.asyncio
async def test_llm_success():
    with patch("app.services.model_registry.ModelRegistry.get_eligible_llm_models") as mock_get_models:
        mock_get_models.return_value = [LLMModelConfig("test_success", "test_success_model", 1, ["json"])]
        with patch("app.services.llm_provider.LLMProviderFactory.get_provider") as mock_get_provider:
            mock_get_provider.return_value = SuccessProvider()
            result = await LLMProviderFactory.generate_with_fallback("test", {})
            assert result == {"result": "success"}

@pytest.mark.asyncio
async def test_llm_fallback_on_429():
    with patch("app.services.model_registry.ModelRegistry.get_eligible_llm_models") as mock_get_models:
        mock_get_models.return_value = [
            LLMModelConfig("test_ratelimit", "test_ratelimit_model", 1, ["json"]),
            LLMModelConfig("test_success", "test_success_model", 2, ["json"])
        ]
        with patch("app.services.llm_provider.LLMProviderFactory.get_provider") as mock_get_provider:
            def side_effect(name):
                if name == "test_ratelimit": return RateLimitProvider()
                return SuccessProvider()
            mock_get_provider.side_effect = side_effect
            
            result = await LLMProviderFactory.generate_with_fallback("test", {})
            assert result == {"result": "success"}
            # The ratelimited model should be placed on cooldown
            assert "test_ratelimit_model" in model_registry._llm_cooldowns

@pytest.mark.asyncio
async def test_llm_fallback_on_5xx():
    with patch("app.services.model_registry.ModelRegistry.get_eligible_llm_models") as mock_get_models:
        mock_get_models.return_value = [
            LLMModelConfig("test_5xx", "test_5xx_model", 1, ["json"]),
            LLMModelConfig("test_success", "test_success_model", 2, ["json"])
        ]
        with patch("app.services.llm_provider.LLMProviderFactory.get_provider") as mock_get_provider:
            def side_effect(name):
                if name == "test_5xx": return ServerErrorProvider()
                return SuccessProvider()
            mock_get_provider.side_effect = side_effect
            
            result = await LLMProviderFactory.generate_with_fallback("test", {})
            assert result == {"result": "success"}
            assert "test_5xx_model" in model_registry._llm_cooldowns

@pytest.mark.asyncio
async def test_llm_fallback_on_timeout():
    with patch("app.services.model_registry.ModelRegistry.get_eligible_llm_models") as mock_get_models:
        mock_get_models.return_value = [
            LLMModelConfig("test_timeout", "test_timeout_model", 1, ["json"]),
            LLMModelConfig("test_success", "test_success_model", 2, ["json"])
        ]
        with patch("app.services.llm_provider.LLMProviderFactory.get_provider") as mock_get_provider:
            def side_effect(name):
                if name == "test_timeout": return TimeoutProvider()
                return SuccessProvider()
            mock_get_provider.side_effect = side_effect
            
            result = await LLMProviderFactory.generate_with_fallback("test", {})
            assert result == {"result": "success"}
            assert "test_timeout_model" in model_registry._llm_cooldowns

@pytest.mark.asyncio
async def test_llm_fallback_on_malformed_output():
    with patch("app.services.model_registry.ModelRegistry.get_eligible_llm_models") as mock_get_models:
        mock_get_models.return_value = [
            LLMModelConfig("test_malformed", "test_malformed_model", 1, ["json"]),
            LLMModelConfig("test_success", "test_success_model", 2, ["json"])
        ]
        with patch("app.services.llm_provider.LLMProviderFactory.get_provider") as mock_get_provider:
            def side_effect(name):
                if name == "test_malformed": return MalformedProvider()
                return SuccessProvider()
            mock_get_provider.side_effect = side_effect
            
            result = await LLMProviderFactory.generate_with_fallback("test", {})
            assert result == {"result": "success"}

@pytest.mark.asyncio
async def test_llm_exhausted():
    with patch("app.services.model_registry.ModelRegistry.get_eligible_llm_models") as mock_get_models:
        mock_get_models.return_value = [
            LLMModelConfig("test_ratelimit", "test_ratelimit_model", 1, ["json"]),
        ]
        with patch("app.services.llm_provider.LLMProviderFactory.get_provider") as mock_get_provider:
            mock_get_provider.return_value = RateLimitProvider()
            
            with pytest.raises(LLMExhaustionError):
                await LLMProviderFactory.generate_with_fallback("test", {})
