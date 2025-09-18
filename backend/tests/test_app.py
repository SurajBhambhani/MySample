import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture()
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


def test_healthz(client: TestClient):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_echo(client: TestClient):
    payload = {"message": "hello"}
    r = client.post("/api/echo", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["message"] == "hello"
    assert data["length"] == 5

