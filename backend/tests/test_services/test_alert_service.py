"""Tests for app.services.alert_service — Telegram alerts."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.alert_service import AlertService


def make_settings(bot_token: str = "", chat_id: str = "") -> MagicMock:
    settings = MagicMock()
    settings.telegram_bot_token = bot_token
    settings.telegram_chat_id = chat_id
    return settings


# ── Disabled (no token) ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_alert_returns_false_when_not_configured() -> None:
    service = AlertService(make_settings())
    assert await service.send_alert("test message") is False


@pytest.mark.asyncio
async def test_send_summary_returns_false_when_not_configured() -> None:
    service = AlertService(make_settings())
    assert await service.send_summary("test message") is False


# ── Enabled (with token) ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_alert_calls_telegram_api() -> None:
    service = AlertService(make_settings(bot_token="123:ABC", chat_id="456"))

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.services.alert_service.httpx.AsyncClient", return_value=mock_client):
        result = await service.send_alert("alert message")

    assert result is True
    mock_client.post.assert_awaited_once()
    call_args = mock_client.post.call_args
    assert "123:ABC" in call_args[0][0]
    assert call_args[1]["json"]["chat_id"] == "456"
    assert "⚠️" in call_args[1]["json"]["text"]


@pytest.mark.asyncio
async def test_send_summary_calls_telegram_api() -> None:
    service = AlertService(make_settings(bot_token="123:ABC", chat_id="456"))

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.services.alert_service.httpx.AsyncClient", return_value=mock_client):
        result = await service.send_summary("summary message")

    assert result is True
    call_args = mock_client.post.call_args
    assert "✅" in call_args[1]["json"]["text"]


@pytest.mark.asyncio
async def test_send_alert_returns_false_on_exception() -> None:
    service = AlertService(make_settings(bot_token="123:ABC", chat_id="456"))

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=Exception("network error"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.services.alert_service.httpx.AsyncClient", return_value=mock_client):
        result = await service.send_alert("will fail")

    assert result is False
