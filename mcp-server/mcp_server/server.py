import json
import os
import subprocess
from functools import lru_cache
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv

from mcp.server import FastMCP

from mcp_server.database import Database, DatabaseError, ensure_select_only
from mcp_server.llm import LLMError, create_provider


load_dotenv()

mcp = FastMCP(name="mcp-relay")


@lru_cache(maxsize=1)
def _database() -> Database:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise DatabaseError("DATABASE_URL is not set for MCP server")
    return Database(url)


@lru_cache(maxsize=1)
def _llm_provider():
    return create_provider(os.environ)


async def _llm_chat(messages: List[Dict[str, str]], *, model: Optional[str] = None) -> str:
    provider = _llm_provider()
    try:
        return await provider.chat(messages, model=model)
    except LLMError:
        raise
    except Exception as exc:  # pragma: no cover - defensive wrapper
        raise LLMError(str(exc)) from exc


def _json_error(exc: Exception) -> str:
    return json.dumps({"error": str(exc)})


@mcp.tool(name="health", description="Checks backend /healthz endpoint and returns status")
async def health() -> str:
    backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            response = await client.get(f"{backend_url}/healthz")
            response.raise_for_status()
            return json.dumps(response.json())
    except Exception as exc:
        return json.dumps({"status": "error", "error": str(exc)})


@mcp.tool(name="echo", description="Echo a message and the length")
async def echo(message: str) -> str:
    return json.dumps({"message": message, "length": len(message)})


@mcp.tool(name="db_query", description="Run a read-only SQL query (SELECT only) and return rows as JSON")
async def db_query(sql: str) -> str:
    try:
        ensure_select_only(sql)
        rows = _database().fetch_all(sql)
        return json.dumps(rows, default=str)
    except Exception as exc:
        return _json_error(exc)


@mcp.tool(name="db_insert_echo", description="Insert a row into echo_messages table with given content")
async def db_insert_echo(content: str) -> str:
    try:
        result = _database().execute(
            "INSERT INTO echo_messages(content, created_at) VALUES (%s, NOW()) RETURNING id",
            (content,),
            returning=True,
        )
    except Exception as exc:
        return _json_error(exc)

    if not result:
        return json.dumps({"error": "Failed to insert echo message"})

    return json.dumps({"id": result["id"], "content": content})


def _run(cmd: List[str], cwd: Optional[str] = None, env: Optional[Dict[str, str]] = None) -> str:
    complete_env = os.environ.copy()
    if env:
        complete_env.update(env)
    proc = subprocess.run(cmd, cwd=cwd, env=complete_env, capture_output=True, text=True)
    out = proc.stdout.strip()
    err = proc.stderr.strip()
    if proc.returncode != 0:
        return json.dumps({"ok": False, "code": proc.returncode, "stdout": out, "stderr": err})
    return json.dumps({"ok": True, "stdout": out})


@mcp.tool(name="alembic_upgrade", description="Run Alembic migrations (upgrade head) in backend/")
async def alembic_upgrade() -> str:
    backend_dir = os.getenv("BACKEND_DIR", os.path.join(os.getcwd(), "backend"))
    env = {"DATABASE_URL": os.getenv("DATABASE_URL", "")}
    return _run(["alembic", "upgrade", "head"], cwd=backend_dir, env=env)


@mcp.tool(name="compose_up_dev", description="docker compose up -d --build for dev stack")
async def compose_up_dev() -> str:
    infra_dir = os.path.join(os.getcwd(), "infra")
    return _run(["docker", "compose", "-f", "docker-compose.dev.yml", "up", "-d", "--build"], cwd=infra_dir)


@mcp.tool(name="compose_down_dev", description="docker compose down for dev stack")
async def compose_down_dev() -> str:
    infra_dir = os.path.join(os.getcwd(), "infra")
    return _run(["docker", "compose", "-f", "docker-compose.dev.yml", "down"], cwd=infra_dir)


@mcp.tool(name="compose_logs_dev", description="docker compose logs --tail=100 for dev stack")
async def compose_logs_dev() -> str:
    infra_dir = os.path.join(os.getcwd(), "infra")
    return _run(["docker", "compose", "-f", "docker-compose.dev.yml", "logs", "--tail", "100"], cwd=infra_dir)


@mcp.tool(name="compose_up_prod", description="docker compose up -d --build for prod stack")
async def compose_up_prod() -> str:
    infra_dir = os.path.join(os.getcwd(), "infra")
    return _run(["docker", "compose", "-f", "docker-compose.prod.yml", "up", "-d", "--build"], cwd=infra_dir)


@mcp.tool(name="compose_down_prod", description="docker compose down for prod stack")
async def compose_down_prod() -> str:
    infra_dir = os.path.join(os.getcwd(), "infra")
    return _run(["docker", "compose", "-f", "docker-compose.prod.yml", "down"], cwd=infra_dir)


@mcp.tool(
    name="enhance_message_and_store",
    description=(
        "Fetch a message by id from echo_messages, enhance it with the LLM, "
        "and store the result in echo_messages_enhanced. Returns new enhanced id."
    ),
)
async def enhance_message_and_store(
    source_id: int,
    instructions: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    try:
        row = _database().fetch_one("SELECT id, content FROM echo_messages WHERE id = %s", (source_id,))
    except Exception as exc:
        return _json_error(exc)

    if not row:
        return json.dumps({"error": f"echo_message id {source_id} not found"})

    system = instructions or "Rewrite the user's text to be clearer, concise, and readable without changing meaning."
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": row["content"]},
    ]
    try:
        enhanced = await _llm_chat(messages, model=model)
    except Exception as exc:
        return _json_error(exc)

    try:
        result = _database().execute(
            "INSERT INTO echo_messages_enhanced (source_message_id, enhanced_content) VALUES (%s, %s) RETURNING id",
            (source_id, enhanced),
            returning=True,
        )
    except Exception as exc:
        return _json_error(exc)

    if not result:
        return json.dumps({"error": "Failed to persist enhanced message"})

    return json.dumps({"source_id": source_id, "enhanced_id": result["id"], "enhanced_content": enhanced})


@mcp.tool(name="list_enhanced_for_message", description="List enhanced records for a given echo_messages.id")
async def list_enhanced_for_message(source_id: int, limit: int = 10) -> str:
    try:
        rows = _database().fetch_all(
            """
            SELECT id, source_message_id, enhanced_content, created_at
            FROM echo_messages_enhanced
            WHERE source_message_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (source_id, limit),
        )
        return json.dumps(rows, default=str)
    except Exception as exc:
        return _json_error(exc)


@mcp.tool(name="enhance_text", description="Use LLM to rewrite text to be clearer and more readable")
async def enhance_text(text: str, instructions: Optional[str] = None, model: Optional[str] = None) -> str:
    system = instructions or "Rewrite the user's text to be clearer, concise, and readable without changing meaning."
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": text},
    ]
    try:
        improved = await _llm_chat(messages, model=model)
        return json.dumps({"original": text, "enhanced": improved})
    except Exception as exc:
        return _json_error(exc)


@mcp.tool(
    name="enhance_text_and_store",
    description="Insert a message into echo_messages, enhance it, and store the enriched content with processing metadata.",
)
async def enhance_text_and_store(
    text: str,
    instructions: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    system = instructions or "Rewrite the user's text to be clearer, concise, and readable without changing meaning."
    try:
        message_row = _database().execute(
            "INSERT INTO echo_messages(content, created_at) VALUES (%s, NOW()) RETURNING id",
            (text,),
            returning=True,
        )
    except Exception as exc:
        return _json_error(exc)

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": text},
    ]
    try:
        enhanced = await _llm_chat(messages, model=model)
    except Exception as exc:
        return json.dumps(
            {
                "message_id": message_row["id"],
                "original": text,
                "error": str(exc),
            }
        )

    processing_details = {
        "instructions": system,
        "model": model,
        "provider": os.getenv("LLM_PROVIDER", "openai"),
    }

    payload = json.dumps({"enhanced": enhanced, "processing": processing_details})

    try:
        enhanced_row = _database().execute(
            "INSERT INTO echo_messages_enhanced (source_message_id, enhanced_content) VALUES (%s, %s) RETURNING id",
            (message_row["id"], payload),
            returning=True,
        )
    except Exception as exc:
        return json.dumps(
            {
                "message_id": message_row["id"],
                "original": text,
                "enhanced": enhanced,
                "processing": processing_details,
                "error": str(exc),
            }
        )

    return json.dumps(
        {
            "message_id": message_row["id"],
            "enhanced_id": enhanced_row["id"],
            "original": text,
            "enhanced": enhanced,
            "processing": processing_details,
        }
    )


@mcp.tool(
    name="enhance_recent_messages",
    description="Fetch recent echo_messages from DB and ask LLM to produce a readable summary/clarification",
)
async def enhance_recent_messages(limit: int = 5, style: Optional[str] = None, model: Optional[str] = None) -> str:
    try:
        rows: List[Dict[str, Any]] = _database().fetch_all(
            "SELECT id, content, created_at FROM echo_messages ORDER BY created_at DESC LIMIT %s",
            (limit,),
        )
    except Exception as exc:
        return _json_error(exc)

    if not rows:
        return json.dumps({"summary": "No messages found", "items": []})

    bullet_style = style or (
        "Summarize and clarify each message as bullet points, preserving intent."
        " Return a concise section titled 'Enhanced Messages' followed by bullets."
    )
    text_blob = "\n".join([f"[{row['id']}] {row['content']} (at {row['created_at']})" for row in rows])
    messages = [
        {"role": "system", "content": bullet_style},
        {"role": "user", "content": f"Messages:\n{text_blob}"},
    ]
    try:
        enhanced = await _llm_chat(messages, model=model)
        return json.dumps({"items": rows, "enhanced": enhanced}, default=str)
    except Exception as exc:
        return json.dumps({"items": rows, "error": str(exc)}, default=str)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
