from __future__ import annotations

import httpx

from app.core.config import Settings
from app.core.logging import get_logger

log = get_logger(__name__)


class AlertService:
    def __init__(self, settings: Settings) -> None:
        self.bot_token = settings.telegram_bot_token
        self.chat_id = settings.telegram_chat_id

    async def send_alert(self, message: str) -> bool:
        return await self._send(f"⚠️ {message}")

    async def send_summary(self, message: str) -> bool:
        return await self._send(f"✅ {message}")

    async def _send(self, text: str) -> bool:
        if not self.bot_token or not self.chat_id:
            return False
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                    json={"chat_id": self.chat_id, "text": text},
                )
                response.raise_for_status()
                return True
        except Exception:
            log.exception("telegram_send_failed")
            return False
