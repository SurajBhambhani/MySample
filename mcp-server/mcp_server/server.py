import asyncio
import json
import os
import re
import shlex
import subprocess
from typing import Any, Dict, List, Optional

import httpx
import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

from mcp.server import FastMCP


load_dotenv()

mcp = FastMCP(name="sample-mcp-server")


def _db_connect():
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set for MCP server")
    conn = psycopg2.connect(url, cursor_factory=RealDictCursor)
    return conn


#############################
# LLM Provider Integration  #
#############################

class LLMError(Exception):
    pass


async def _llm_chat(messages: List[Dict[str, str]], *, model: Optional[str] = None) -> str:
    """Call a pluggable LLM provider using simple chat interface.

    Supported providers via env var LLM_PROVIDER: openai | anthropic | openrouter | azure_openai
    Required env vars per provider:
    - openai: OPENAI_API_KEY, LLM_MODEL (e.g., gpt-4o-mini)
    - anthropic: ANTHROPIC_API_KEY, LLM_MODEL (e.g., claude-3-5-sonnet-20240620)
    - openrouter: OPENROUTER_API_KEY, LLM_MODEL (e.g., openrouter/auto | meta-llama/...) 
    - azure_openai: AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT
    """
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    chosen_model = model or os.getenv("LLM_MODEL")

    async with httpx.AsyncClient(timeout=30) as client:
        if provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise LLMError("OPENAI_API_KEY not set")
            if not chosen_model:
                chosen_model = "gpt-4o-mini"
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": chosen_model, "messages": messages},
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()

        elif provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise LLMError("ANTHROPIC_API_KEY not set")
            if not chosen_model:
                chosen_model = "claude-3-5-sonnet-20240620"
            # Map OpenAI-style messages to Anthropic
            system_text = "\n".join(m["content"] for m in messages if m.get("role") == "system")
            content = []
            for m in messages:
                if m["role"] == "user":
                    content.append({"role": "user", "content": m["content"]})
                elif m["role"] == "assistant":
                    content.append({"role": "assistant", "content": m["content"]})
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": chosen_model,
                    "system": system_text or None,
                    "messages": content,
                    "max_tokens": 1024,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return "".join(block.get("text", "") for block in data.get("content", [])).strip()

        elif provider == "openrouter":
            api_key = os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                raise LLMError("OPENROUTER_API_KEY not set")
            if not chosen_model:
                chosen_model = os.getenv("LLM_MODEL", "openrouter/auto")
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                },
                json={"model": chosen_model, "messages": messages},
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()

        elif provider == "ollama":
            endpoint = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434").rstrip("/")
            model_name = model or os.getenv("OLLAMA_MODEL", "llama3")
            payload: Dict[str, Any] = {
                "model": model_name,
                "messages": messages,
            }
            payload["stream"] = False
            options = os.getenv("OLLAMA_OPTIONS")
            if options:
                try:
                    payload["options"] = json.loads(options)
                except json.JSONDecodeError:
                    pass
            resp = await client.post(f"{endpoint}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            message = data.get("message", {}).get("content")
            if not message:
                raise LLMError("Ollama response missing message content")
            return message.strip()

        elif provider == "azure_openai":
            api_key = os.getenv("AZURE_OPENAI_API_KEY")
            endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
            api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-05-01-preview")
            if not all([api_key, endpoint, deployment]):
                raise LLMError("AZURE_OPENAI_* env vars not set")
            url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
            resp = await client.post(
                url,
                headers={"api-key": api_key},
                json={"messages": messages},
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()

        else:
            raise LLMError(f"Unsupported LLM_PROVIDER: {provider}")


@mcp.tool(name="health", description="Checks backend /healthz endpoint and returns status")
async def health() -> str:
    backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(f"{backend_url}/healthz")
            r.raise_for_status()
            return json.dumps(r.json())
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)})


@mcp.tool(name="echo", description="Echo a message and the length")
async def echo(message: str) -> str:
    return json.dumps({"message": message, "length": len(message)})


@mcp.tool(name="db_query", description="Run a read-only SQL query (SELECT only) and return rows as JSON")
async def db_query(sql: str) -> str:
    if not re.match(r"^\s*select\s", sql, re.IGNORECASE):
        return json.dumps({"error": "Only SELECT queries are allowed"})
    with _db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            return json.dumps(rows, default=str)


@mcp.tool(name="db_insert_echo", description="Insert a row into echo_messages table with given content")
async def db_insert_echo(content: str) -> str:
    with _db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO echo_messages(content, created_at) VALUES (%s, NOW()) RETURNING id",
                (content,),
            )
            new_id = cur.fetchone()["id"]
            conn.commit()
            return json.dumps({"id": new_id, "content": content})


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
async def enhance_message_and_store(source_id: int, instructions: Optional[str] = None, model: Optional[str] = None) -> str:
    # Read original content
    with _db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, content FROM echo_messages WHERE id = %s", (source_id,))
            row = cur.fetchone()
            if not row:
                return json.dumps({"error": f"echo_message id {source_id} not found"})
            content = row["content"]

    # Enhance via LLM
    system = instructions or "Rewrite the user's text to be clearer, concise, and readable without changing meaning."
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": content},
    ]
    try:
        enhanced = await _llm_chat(messages, model=model)
    except Exception as e:
        return json.dumps({"error": str(e)})

    # Store enhanced
    with _db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO echo_messages_enhanced (source_message_id, enhanced_content) VALUES (%s, %s) RETURNING id",
                (source_id, enhanced),
            )
            new_id = cur.fetchone()["id"]
            conn.commit()
    return json.dumps({"source_id": source_id, "enhanced_id": new_id, "enhanced_content": enhanced})


@mcp.tool(name="list_enhanced_for_message", description="List enhanced records for a given echo_messages.id")
async def list_enhanced_for_message(source_id: int, limit: int = 10) -> str:
    with _db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, source_message_id, enhanced_content, created_at
                FROM echo_messages_enhanced
                WHERE source_message_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (source_id, limit),
            )
            rows = cur.fetchall()
            return json.dumps(rows, default=str)

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
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool(
    name="enhance_recent_messages",
    description="Fetch recent echo_messages from DB and ask LLM to produce a readable summary/clarification",
)
async def enhance_recent_messages(limit: int = 5, style: Optional[str] = None, model: Optional[str] = None) -> str:
    # Pull last N messages from DB
    with _db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, content, created_at FROM echo_messages ORDER BY created_at DESC LIMIT %s",
                (limit,),
            )
            rows: List[Dict[str, Any]] = cur.fetchall()

    if not rows:
        return json.dumps({"summary": "No messages found", "items": []})

    # Build prompt
    bullet_style = style or (
        "Summarize and clarify each message as bullet points, preserving intent."
        " Return a concise section titled 'Enhanced Messages' followed by bullets."
    )
    text_blob = "\n".join([f"[{r['id']}] {r['content']} (at {r['created_at']})" for r in rows])
    messages = [
        {"role": "system", "content": bullet_style},
        {"role": "user", "content": f"Messages:\n{text_blob}"},
    ]
    try:
        enhanced = await _llm_chat(messages, model=model)
        return json.dumps({"items": rows, "enhanced": enhanced}, default=str)
    except Exception as e:
        return json.dumps({"items": rows, "error": str(e)}, default=str)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
