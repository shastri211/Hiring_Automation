from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings

# See Settings.DB_SCHEMA - set only by the test suite, to isolate every
# connection this engine ever hands out onto a dedicated schema rather than
# "public", so tests can never touch real dev data. Deliberately excludes
# "public" from the search_path (no fallback) - including it here once
# caused every unqualified table lookup that didn't yet exist in the test
# schema (e.g. alembic_version on a fresh schema) to silently resolve to
# the real public table instead, which is exactly the accidental-real-data
# access this whole mechanism exists to prevent.
_connect_args = {"server_settings": {"search_path": settings.DB_SCHEMA}} if settings.DB_SCHEMA else {}

engine = create_async_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    pool_pre_ping=True,
    echo=False,
    connect_args=_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
