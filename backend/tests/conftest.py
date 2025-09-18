import os
import sys
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


@pytest.fixture(autouse=True)
def _ensure_test_env(monkeypatch):
    """Force predictable settings for tests and reset cache after each run."""

    from app.config import get_settings

    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", os.getenv("DATABASE_URL", "sqlite:///:memory:"))
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost, http://testserver")

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
