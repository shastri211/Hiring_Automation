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


# --- Auth test-compatibility ---------------------------------------------
#
# Every route except health/auth/public_interview (and, within the
# integration router, /interview/trigger) now requires a logged-in HR user
# via app.api.deps.get_current_user. The 267 pre-existing tests hit real
# endpoints through the `client`/`test_client` fixtures above and know
# nothing about auth, so this autouse fixture overrides get_current_user for
# the whole suite to return a fixed in-memory test user - the standard
# FastAPI dependency-override testing pattern. No existing test needs to
# change.
#
# tests/test_auth.py deliberately exercises the *real* dependency instead,
# via its own fixture that pops this override for the duration of each of
# its tests (see tests/test_auth.py).
@pytest.fixture(autouse=True)
def _override_get_current_user():
    from app.main import app
    from app.api.deps import get_current_user
    from app.models.user import User

    test_user = User(
        id=1,
        email="test-user@example.com",
        hashed_password="unused-in-tests",
        name="Test User",
        is_active=True,
    )

    app.dependency_overrides[get_current_user] = lambda: test_user
    yield
    app.dependency_overrides.pop(get_current_user, None)
