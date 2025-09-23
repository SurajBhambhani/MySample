import json
import os
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv

from mcp.server import FastMCP

from mcp_server.database import Database, DatabaseError, ensure_select_only
from mcp_server.llm import LLMError, create_provider
from mcp_server.rag_store import RAGError, build_default_store


load_dotenv()

mcp = FastMCP(name="mcp-relay")


@lru_cache(maxsize=1)
def _database() -> Database:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise DatabaseError("DATABASE_URL is not set for MCP server")
    return Database(url)


def _maybe_database() -> Optional[Database]:
    try:
        return _database()
    except DatabaseError:
        return None


@lru_cache(maxsize=1)
def _llm_provider():
    return create_provider(os.environ)


def _rag_enabled() -> bool:
    return os.getenv("RAG_ENABLED", "true").lower() not in {"0", "false", "no"}


@lru_cache(maxsize=1)
def _rag_store():
    if not _rag_enabled():
        raise RAGError("RAG is disabled via RAG_ENABLED")
    return build_default_store()


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


async def _inject_rag_context(query: str, messages: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
    if not _rag_enabled():
        return {"enabled": False}
    try:
        store = _rag_store()
    except RAGError as exc:
        return {"enabled": False, "error": str(exc)}

    try:
        limit = int(os.getenv("RAG_TOP_K", "3"))
    except ValueError:
        limit = 3

    try:
        results = await store.query(text=query, limit=limit)
    except Exception as exc:  # pragma: no cover - defensive
        return {"enabled": True, "error": str(exc)}

    if not results:
        return {"enabled": True, "matches": []}

    context_lines: List[str] = []
    matches: List[Dict[str, Any]] = []
    for doc in results:
        label = doc.source or doc.store or f"doc#{doc.id}"
        store_name = doc.store or getattr(store, "name", "default")
        context_lines.append(f"[{label}] (store={store_name})\n{doc.content}")
        matches.append(
            {
                "id": doc.id,
                "source": doc.source,
                "store": store_name,
                "score": round(doc.score, 4),
            }
        )

    messages.insert(
        1,
        {
            "role": "system",
            "content": "Knowledge base context you may cite if useful:\n" + "\n\n".join(context_lines),
        },
    )

    return {"enabled": True, "matches": matches}


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


@mcp.tool(name="rag_upsert", description="Insert or update text in the RAG knowledge base")
async def rag_upsert(content: str, source: Optional[str] = None, store: Optional[str] = None) -> str:
    try:
        rag_store = _rag_store()
    except Exception as exc:  # pragma: no cover - cache errors
        return _json_error(exc)

    try:
        doc_id = await rag_store.upsert(source=source, content=content, store=store)
        resolved_store = store
        if not resolved_store:
            if ":" in doc_id:
                resolved_store = doc_id.split(":", 1)[0]
            else:
                resolved_store = getattr(rag_store, "name", None)
        payload = {"id": doc_id, "source": source, "store": resolved_store}
        return json.dumps(payload)
    except Exception as exc:
        return _json_error(exc)


@mcp.tool(name="rag_search", description="Search the RAG knowledge base for relevant entries")
async def rag_search(query: str, limit: int = 3, store: Optional[str] = None) -> str:
    try:
        rag_store = _rag_store()
    except Exception as exc:
        return _json_error(exc)

    try:
        selected = None
        if store:
            selected = [item.strip() for item in store.split(",") if item.strip()]
        results = await rag_store.query(text=query, limit=limit, stores=selected)
        return json.dumps(
            [
                {
                    "id": doc.id,
                    "source": doc.source,
                    "content": doc.content,
                    "store": doc.store,
                    "score": round(doc.score, 4),
                }
                for doc in results
            ]
        )
    except Exception as exc:
        return _json_error(exc)


@mcp.tool(name="rag_sources", description="List configured RAG store identifiers")
async def rag_sources() -> str:
    try:
        rag_store = _rag_store()
    except Exception as exc:
        return _json_error(exc)

    names = getattr(rag_store, "store_names", None)
    if names is None:
        names = [getattr(rag_store, "name", "default")]
    return json.dumps(names)


@mcp.tool(
    name="rag_import",
    description="Load content from a local file path or HTTP(S) URL into the RAG knowledge base",
)
async def rag_import(location: str, store: Optional[str] = None, source: Optional[str] = None) -> str:
    try:
        store_instance = _rag_store()
    except Exception as exc:
        return _json_error(exc)

    if location.startswith("http://") or location.startswith("https://"):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(location)
                resp.raise_for_status()
                content = resp.text
        except Exception as exc:
            return _json_error(exc)
        resolved_source = source or location
    else:
        path = Path(location).expanduser()
        if not path.exists():
            return _json_error(RAGError(f"File not found: {path}"))
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as exc:
            return _json_error(exc)
        resolved_source = source or str(path)

    try:
        doc_id = await store_instance.upsert(source=resolved_source, content=content, store=store)
        resolved_store = store
        if not resolved_store:
            if ":" in doc_id:
                resolved_store = doc_id.split(":", 1)[0]
            else:
                resolved_store = getattr(store_instance, "name", None)
        payload = {"id": doc_id, "source": resolved_source, "store": resolved_store}
        return json.dumps(payload)
    except Exception as exc:
        return _json_error(exc)


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

    system = instructions or (
        "Act as a support engineer. Using any knowledge base context provided, identify the root cause of the"
        " user's issue and outline concrete resolution steps. If the context is insufficient, say so explicitly."
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": row["content"]},
    ]
    rag_info = await _inject_rag_context(row["content"], messages)
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

    response: Dict[str, Any] = {
        "source_id": source_id,
        "enhanced_id": result["id"],
        "enhanced_content": enhanced,
    }
    if rag_info:
        response["rag"] = rag_info
    return json.dumps(response)


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
    system = instructions or (
        "Act as a support engineer. Using any knowledge base context provided, identify the root cause of the"
        " user's issue and outline concrete resolution steps. If the context is insufficient, say so explicitly."
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": text},
    ]
    rag_info = await _inject_rag_context(text, messages)
    try:
        improved = await _llm_chat(messages, model=model)
        payload = {"original": text, "enhanced": improved}
        if rag_info:
            payload["rag"] = rag_info
        return json.dumps(payload)
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
    system = instructions or (
        "Act as a support engineer. Using any knowledge base context provided, identify the root cause of the"
        " user's issue and outline concrete resolution steps. If the context is insufficient, say so explicitly."
    )
    db = _maybe_database()
    message_id: Optional[int] = None
    enhanced_id: Optional[int] = None
    storage_error: Optional[str] = None

    if db is None:
        storage_error = "Database not configured"
    else:
        try:
            message_row = db.execute(
                "INSERT INTO echo_messages(content, created_at) VALUES (%s, NOW()) RETURNING id",
                (text,),
                returning=True,
            )
            if message_row and "id" in message_row:
                message_id = message_row["id"]
            else:
                storage_error = "Failed to insert echo message"
        except Exception as exc:
            storage_error = str(exc)

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": text},
    ]
    rag_info = await _inject_rag_context(text, messages)
    try:
        enhanced = await _llm_chat(messages, model=model)
    except Exception as exc:
        payload: Dict[str, Any] = {
            "message_id": message_id,
            "original": text,
            "error": str(exc),
        }
        if rag_info:
            payload["rag"] = rag_info
        if storage_error:
            payload["storage_error"] = storage_error
        return json.dumps(payload)

    processing_payload = {
        "instructions": system,
        "model": model,
        "provider": os.getenv("LLM_PROVIDER", "openai"),
    }
    if rag_info:
        processing_payload["rag"] = rag_info

    if db and storage_error is None and message_id is not None:
        payload_to_store = json.dumps({"enhanced": enhanced, "processing": processing_payload})
        try:
            enhanced_row = db.execute(
                "INSERT INTO echo_messages_enhanced (source_message_id, enhanced_content) VALUES (%s, %s) RETURNING id",
                (message_id, payload_to_store),
                returning=True,
            )
            if enhanced_row and "id" in enhanced_row:
                enhanced_id = enhanced_row["id"]
            else:
                storage_error = "Failed to persist enhanced message"
        except Exception as exc:
            storage_error = str(exc)

    processing_details = dict(processing_payload)
    processing_details["persisted"] = enhanced_id is not None
    if storage_error:
        processing_details["storage_error"] = storage_error

    return json.dumps(
        {
            "message_id": message_id,
            "enhanced_id": enhanced_id,
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
