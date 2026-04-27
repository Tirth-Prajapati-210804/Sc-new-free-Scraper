from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

_settings = get_settings()


def _connect_args() -> dict:
    """asyncpg connect args tuned for Supabase / pgbouncer compatibility.

    Supabase's pooler (port 6543) runs pgbouncer in *transaction* mode, which
    breaks asyncpg's prepared-statement cache (`prepared statement
    "__asyncpg_stmt_X__" already exists`). Disabling the cache and naming
    statements lets the same connection be reused across pgbouncer txns.

    For direct connections (port 5432) these flags are harmless — they just
    skip a small per-statement cache that we don't lean on.
    """
    return {"statement_cache_size": 0}


engine = create_async_engine(
    _settings.database_url,
    pool_pre_ping=True,         # verify connection before use
    pool_size=5,
    max_overflow=10,
    pool_recycle=1800,          # recycle connections every 30 min
    pool_timeout=30,
    connect_args=_connect_args(),
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
