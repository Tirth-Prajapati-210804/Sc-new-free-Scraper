from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from dotenv import load_dotenv
load_dotenv()

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.base import Base
import app.models  # noqa: F401 — registers all models with Base.metadata

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError(
            "DATABASE_URL environment variable is required. "
            "Set it in your .env file or environment."
        )
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = create_async_engine(get_url())
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def do_run_migrations(connection: object) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)  # type: ignore[arg-type]
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
