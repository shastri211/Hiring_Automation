import pytest
from unittest.mock import patch, AsyncMock
from app.services.profiler import profiler_service

@pytest.mark.asyncio
async def test_profiler_missing_api_key():
    with patch("app.services.profiler.LLMProviderFactory.generate_with_fallback", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = {"name": "Test User"}
        result = await profiler_service.profile_candidate("some resume text")
        assert result == {"name": "Test User"}
        mock_gen.assert_called_once()
