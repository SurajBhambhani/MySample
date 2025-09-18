import os
import sys
from pathlib import Path

import pytest


MCP_ROOT = Path(__file__).resolve().parents[1]
if str(MCP_ROOT) not in sys.path:
    sys.path.insert(0, str(MCP_ROOT))


@pytest.fixture(autouse=True)
def _default_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", os.getenv("DATABASE_URL", "sqlite:///:memory:"))
    yield
