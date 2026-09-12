import os
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
import pytest
from httpx import AsyncClient, ASGITransport
import asyncio
from unittest.mock import patch, AsyncMock

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(autouse=True)
def mock_llm_providers():
    with patch('app.services.llm_provider.GroqProvider.generate_json', new_callable=AsyncMock) as mock_groq, \
         patch('app.services.llm_provider.GeminiProvider.generate_json', new_callable=AsyncMock) as mock_gemini, \
         patch('app.core.config.settings.GROQ_API_KEY', 'dummy_groq'), \
         patch('app.core.config.settings.GEMINI_API_KEY', 'dummy_gemini'), \
         patch('app.core.config.settings.QDRANT_URL', 'http://dummy:6333'), \
         patch('app.core.config.settings.QDRANT_API_KEY', 'dummy'):
        
        mock_groq.return_value = {"title": "Test", "score": 90, "decision": "SHORTLIST"}
        mock_gemini.return_value = {"title": "Test", "score": 90, "decision": "SHORTLIST"}
        yield

@pytest.fixture
async def db_session():
    from app.worker import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        yield session

@pytest.fixture
async def test_client():
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
@pytest.fixture
async def client():
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
