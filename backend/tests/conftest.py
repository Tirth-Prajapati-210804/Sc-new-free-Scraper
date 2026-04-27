from __future__ import annotations

import os

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/flight_data_scrapper_test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-testing-only-12345")
os.environ.setdefault("ADMIN_EMAIL", "admin@test.com")
os.environ.setdefault("ADMIN_PASSWORD", "testpassword123")
