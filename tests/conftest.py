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


# --- DB isolation ----------------------------------------------------------
#
# There was no separate test database - db_session/client ran against the
# real dev Postgres via the app's actual AsyncSessionLocal. Every
# `session.commit()` anywhere the suite touched permanently wrote into that
# live database; a single afternoon of repeated full-suite runs once left
# 567 fake Job rows (plus their cascading Resume/Candidate/etc. data)
# sitting in it.
#
# A per-test rollback-transaction wrapper was tried first (SAVEPOINT-based,
# via join_transaction_mode="create_savepoint") and rejected: this app has
# dozens of `async with AsyncSessionLocal() as session:` call sites spread
# across services/worker code, each opening its own independent Session
# object. Interleaving several such Session objects on one shared
# connection - e.g. a test's own db_session fixture staying open while an
# HTTP call under test opens and commits a second, separate Session on that
# same connection - corrupts Postgres's SAVEPOINT stack: a row committed by
# one Session's SAVEPOINT silently became invisible to a sibling Session's
# very next query, with no error raised. Confirmed by direct reproduction
# during this fix.
#
# Instead, Settings.DB_SCHEMA (set via pytest.ini's `env`) points every
# connection the app's engine ever opens at a dedicated Postgres schema
# ("test_isolation", migrated once via `DB_SCHEMA=test_isolation alembic
# upgrade head`) instead of "public" - see app/db/session.py. Tests can
# commit freely with zero special-casing; they physically cannot reach real
# dev data. This fixture just truncates that schema once per test session
# (not per-test - cheap, and leftover fixture data within a run is
# harmless) so repeated runs over time don't accumulate rows indefinitely,
# the same growth problem confined to a schema where it can't hurt anything.
@pytest.fixture(scope="session", autouse=True)
async def _reset_test_schema():
    from app.core.config import settings
    from app.db.session import engine
    from sqlalchemy import text

    if not settings.DB_SCHEMA:
        raise RuntimeError(
            "Settings.DB_SCHEMA is not set - refusing to run the test suite, since "
            "it would otherwise write directly into the real dev database. Check "
            "pytest.ini's `env` section (DB_SCHEMA=test_isolation)."
        )

    async with engine.begin() as conn:
        tables = (
            await conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = :schema AND table_name != 'alembic_version'"
                ),
                {"schema": settings.DB_SCHEMA},
            )
        ).scalars().all()
        if tables:
            quoted = ", ".join(f'"{t}"' for t in tables)
            await conn.execute(text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE"))

    yield

@pytest.fixture(autouse=True)
def mock_llm_providers():
    with patch('app.services.llm_provider.GroqProvider.generate_json', new_callable=AsyncMock) as mock_groq, \
         patch('app.services.llm_provider.GeminiProvider.generate_json', new_callable=AsyncMock) as mock_gemini, \
         patch('app.core.config.settings.GROQ_API_KEY', 'dummy_groq'), \
         patch('app.core.config.settings.GEMINI_API_KEY', 'dummy_gemini'), \
         patch('app.core.config.settings.QDRANT_URL', 'http://dummy:6333'), \
         patch('app.core.config.settings.QDRANT_API_KEY', 'dummy'), \
         patch('app.core.config.settings.COOKIE_SECURE', False):
        
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
