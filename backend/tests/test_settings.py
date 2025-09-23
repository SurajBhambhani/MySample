import pytest

from app.config import get_settings, Settings


def _with_env(monkeypatch, **env):
    for key, value in env.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)


@pytest.mark.parametrize(
    "cors_value, expected",
    [
        ("*", ["*"]),
        ("https://a.com, https://b.com", ["https://a.com", "https://b.com"]),
        ("[\"https://json.com\", \"https://list.com\"]", ["https://json.com", "https://list.com"]),
        ("", ["*"]),
    ],
)
def test_cors_parsing(monkeypatch, cors_value, expected):
    """Settings should normalise multiple CORS representations."""

    _with_env(
        monkeypatch,
        DATABASE_URL="sqlite:///:memory:",
        CORS_ORIGINS=cors_value,
    )

    get_settings.cache_clear()
    settings = get_settings()
    assert settings.cors_origins == expected


def test_database_url_optional(monkeypatch):
    """DATABASE_URL can be unset and surface as None."""

    _with_env(monkeypatch, DATABASE_URL=None)

    get_settings.cache_clear()
    settings = get_settings()

    assert settings.database_url is None


def test_session_scope_without_database_fails(monkeypatch):
    import importlib
    import sys

    _with_env(monkeypatch, DATABASE_URL=None)

    get_settings.cache_clear()

    sys.modules.pop("app.db", None)
    db_module = importlib.import_module("app.db")

    with pytest.raises(RuntimeError):
        with db_module.session_scope():
            pass
