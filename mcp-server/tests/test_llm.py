import asyncio
from types import SimpleNamespace


class DummyResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class DummyAsyncClient:
    def __init__(self, *, payload, capture):
        self.payload = payload
        self.capture = capture

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json):
        self.capture.append(SimpleNamespace(url=url, json=json))
        return DummyResponse(self.payload)


def test_llm_chat_uses_ollama_payload(monkeypatch):
    from mcp_server import server as mcp_server

    calls = []
    response = {"message": {"content": "enhanced"}}

    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_ENDPOINT", "http://localhost:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3")

    def fake_async_client(**kwargs):
        return DummyAsyncClient(payload=response, capture=calls)

    monkeypatch.setitem(mcp_server.__dict__, "httpx", SimpleNamespace(AsyncClient=fake_async_client))

    result = asyncio.run(mcp_server._llm_chat([{"role": "user", "content": "hi"}]))

    assert result == "enhanced"
    assert len(calls) == 1
    sent = calls[0].json
    assert sent["model"] == "llama3"
    assert sent["stream"] is False
    assert sent["messages"][0]["content"] == "hi"
