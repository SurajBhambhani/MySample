import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

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
    """Proxy to the MCP server's enhance_text tool and parse its JSON output."""

    raw = await mcp_server.enhance_text(text=text, instructions=instructions, model=model)
    data = json.loads(raw)

    if "error" in data:
        raise HTTPException(status_code=502, detail=data["error"])

    return data
