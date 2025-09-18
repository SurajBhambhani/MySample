import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture()
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


def test_healthz(client: TestClient):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_echo_round_trip(client: TestClient):
    payload = {"message": "hello"}
    response = client.post("/api/echo", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data == {"message": "hello", "length": 5}


def test_echo_requires_message_field(client: TestClient):
    response = client.post("/api/echo", json={})
    assert response.status_code == 422
    detail = response.json()["detail"][0]
    assert detail["loc"][-1] == "message"
    assert detail["type"] == "missing"


def test_app_has_cors_middleware(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("CORS_ORIGINS", "https://example.com, https://another.com")

    from app.config import get_settings

    get_settings.cache_clear()
    app = create_app()
    origins = next(
        (middleware.kwargs.get("allow_origins") for middleware in app.user_middleware if middleware.cls.__name__ == "CORSMiddleware"),
        None,
    )
    assert origins == ["https://example.com", "https://another.com"]


def test_enhance_endpoint_success(monkeypatch, client: TestClient):
    async def fake_enhance_text(*, text, instructions=None, model=None):
        assert text == "hello"
        return {"original": text, "enhanced": "HELLO"}

    monkeypatch.setattr("app.main.enhance_with_mcp", fake_enhance_text)

    response = client.post("/api/enhance", json={"text": "hello"})
    assert response.status_code == 200
    assert response.json() == {"original": "hello", "enhanced": "HELLO"}


def test_enhance_endpoint_error(monkeypatch, client: TestClient):
    async def fake_enhance_text(*, text, instructions=None, model=None):
        raise HTTPException(status_code=502, detail="llm down")

    monkeypatch.setattr("app.main.enhance_with_mcp", fake_enhance_text)

    response = client.post("/api/enhance", json={"text": "hello"})
    assert response.status_code == 502
    assert response.json()["detail"] == "llm down"
