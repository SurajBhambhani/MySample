import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from fastapi import HTTPException


REPO_ROOT = Path(__file__).resolve().parents[3]
MCP_ROOT = REPO_ROOT / "mcp-server"
if MCP_ROOT.exists() and str(MCP_ROOT) not in sys.path:
    sys.path.insert(0, str(MCP_ROOT))

try:
    from mcp_server import server as mcp_server
except ModuleNotFoundError as exc:  # pragma: no cover - defensive
    raise RuntimeError(
        "MCP server package is not available. Ensure dependencies are installed via make setup."
    ) from exc


async def enhance_text(
    *, text: str, instructions: Optional[str] = None, model: Optional[str] = None
) -> Dict[str, Any]:
    """Proxy to the MCP server's enhance_text_and_store tool and parse its JSON output."""

    raw = await mcp_server.enhance_text_and_store(text=text, instructions=instructions, model=model)
    data = json.loads(raw)

    if "error" in data:
        raise HTTPException(status_code=502, detail=data["error"])

    return data


def _ensure_ok(payload: Any) -> Any:
    if isinstance(payload, dict) and "error" in payload:
        raise HTTPException(status_code=502, detail=str(payload["error"]))
    return payload


async def rag_sources() -> List[str]:
    raw = await mcp_server.rag_sources()
    data = json.loads(raw)
    _ensure_ok(data)
    if not isinstance(data, list):
        raise HTTPException(status_code=502, detail="Unexpected response from rag_sources")
    return [str(item) for item in data]


async def rag_import(location: str, *, store: Optional[str] = None, source: Optional[str] = None) -> Dict[str, Any]:
    raw = await mcp_server.rag_import(location=location, store=store, source=source)
    data = json.loads(raw)
    _ensure_ok(data)
    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="Unexpected response from rag_import")
    return data


async def rag_upsert_text(content: str, *, store: Optional[str] = None, source: Optional[str] = None) -> Dict[str, Any]:
    raw = await mcp_server.rag_upsert(content=content, store=store, source=source)
    data = json.loads(raw)
    _ensure_ok(data)
    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="Unexpected response from rag_upsert")
    return data


async def rag_search(
    *, query: str, limit: int = 3, stores: Optional[Sequence[str]] = None
) -> List[Dict[str, Any]]:
    store_param = ",".join(stores) if stores else None
    raw = await mcp_server.rag_search(query=query, limit=limit, store=store_param)
    data = json.loads(raw)
    _ensure_ok(data)
    if not isinstance(data, list):
        raise HTTPException(status_code=502, detail="Unexpected response from rag_search")
    return data
