"""Tests for app.core.rate_limit — sliding window rate limiter."""
from __future__ import annotations

import time

from app.core.rate_limit import (
    SlidingWindowRateLimiter,
    build_rate_limit_key,
    unwrap_client_host,
)


# ── SlidingWindowRateLimiter ─────────────────────────────────────────────────

def test_limiter_allows_under_limit() -> None:
    limiter = SlidingWindowRateLimiter()
    assert limiter.hit("key1", limit=3, window_seconds=60) == 0
    assert limiter.hit("key1", limit=3, window_seconds=60) == 0
    assert limiter.hit("key1", limit=3, window_seconds=60) == 0


def test_limiter_blocks_over_limit() -> None:
    limiter = SlidingWindowRateLimiter()
    for _ in range(3):
        limiter.hit("key2", limit=3, window_seconds=60)
    retry_after = limiter.hit("key2", limit=3, window_seconds=60)
    assert retry_after > 0


def test_limiter_different_keys_are_independent() -> None:
    limiter = SlidingWindowRateLimiter()
    for _ in range(3):
        limiter.hit("keyA", limit=3, window_seconds=60)
    # keyA is exhausted
    assert limiter.hit("keyA", limit=3, window_seconds=60) > 0
    # keyB is fresh
    assert limiter.hit("keyB", limit=3, window_seconds=60) == 0


def test_limiter_reset_clears_key() -> None:
    limiter = SlidingWindowRateLimiter()
    for _ in range(3):
        limiter.hit("key3", limit=3, window_seconds=60)
    assert limiter.hit("key3", limit=3, window_seconds=60) > 0
    limiter.reset("key3")
    assert limiter.hit("key3", limit=3, window_seconds=60) == 0


def test_limiter_reset_nonexistent_key_is_noop() -> None:
    limiter = SlidingWindowRateLimiter()
    limiter.reset("does-not-exist")  # should not raise


def test_retry_after_returns_zero_when_no_entries() -> None:
    limiter = SlidingWindowRateLimiter()
    assert limiter.retry_after("empty", limit=5, window_seconds=60) == 0


def test_retry_after_returns_positive_when_blocked() -> None:
    limiter = SlidingWindowRateLimiter()
    for _ in range(5):
        limiter.add("blocked")
    result = limiter.retry_after("blocked", limit=5, window_seconds=60)
    assert result >= 1


def test_add_without_hit() -> None:
    limiter = SlidingWindowRateLimiter()
    limiter.add("manual")
    limiter.add("manual")
    assert limiter.retry_after("manual", limit=3, window_seconds=60) == 0
    limiter.add("manual")
    assert limiter.retry_after("manual", limit=3, window_seconds=60) > 0


# ── build_rate_limit_key ─────────────────────────────────────────────────────

def test_build_rate_limit_key_basic() -> None:
    key = build_rate_limit_key("login", "192.168.1.1", "user@example.com")
    assert key == "login:192.168.1.1:user@example.com"


def test_build_rate_limit_key_lowercases() -> None:
    key = build_rate_limit_key("login", "IP", "USER@EXAMPLE.COM")
    assert key == "login:ip:user@example.com"


def test_build_rate_limit_key_strips_whitespace() -> None:
    key = build_rate_limit_key("login", " 192.168.1.1 ", " user@example.com ")
    assert key == "login:192.168.1.1:user@example.com"


def test_build_rate_limit_key_skips_empty_parts() -> None:
    key = build_rate_limit_key("login", "", "user@example.com", "  ")
    assert key == "login:user@example.com"


# ── unwrap_client_host ───────────────────────────────────────────────────────

def test_unwrap_with_forwarded_for() -> None:
    result = unwrap_client_host("10.0.0.1", fallback=lambda: "172.16.0.1")
    # Should combine forwarded + direct IP
    assert "10.0.0.1" in result
    assert "172.16.0.1" in result


def test_unwrap_without_forwarded_for() -> None:
    result = unwrap_client_host(None, fallback=lambda: "172.16.0.1")
    assert result == "172.16.0.1"


def test_unwrap_with_multiple_forwarded_ips() -> None:
    result = unwrap_client_host("10.0.0.1, 192.168.1.1", fallback=lambda: "172.16.0.1")
    assert "10.0.0.1" in result


def test_unwrap_rejects_invalid_forwarded_for() -> None:
    """Invalid X-Forwarded-For values (e.g. injection attempts) should be ignored."""
    result = unwrap_client_host(
        "<script>alert(1)</script>",
        fallback=lambda: "172.16.0.1",
    )
    assert result == "172.16.0.1"


def test_unwrap_rejects_empty_forwarded_for() -> None:
    result = unwrap_client_host("", fallback=lambda: "172.16.0.1")
    assert result == "172.16.0.1"
