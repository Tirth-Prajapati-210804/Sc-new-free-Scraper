from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger

log = get_logger(__name__)


async def check_db(session: AsyncSession) -> bool:
    try:
        await session.execute(text("SELECT 1"))
        return True
    except Exception:
        log.warning("db_health_check_failed", exc_info=True)
        return False
