"""CLI helpers for testing MCP enrichment tools without running full MCP server."""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Optional

import typer


# Ensure repository root is importable regardless of cwd
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp_server.server import (  # noqa: E402
    enhance_message_and_store,
    enhance_recent_messages,
    enhance_text,
    list_enhanced_for_message,
)


cli = typer.Typer(help="Utilities for invoking MCP enrichment tools directly.")


def _require_llm_env() -> None:
    provider = os.getenv("LLM_PROVIDER")
    if not provider:
        typer.echo("LLM_PROVIDER env var is not set.", err=True)
        raise typer.Exit(code=2)
    provider = provider.lower()
    key_map = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "azure_openai": "AZURE_OPENAI_API_KEY",
    }
    api_env = key_map.get(provider)
    if api_env and not os.getenv(api_env):
        typer.echo(f"Environment variable {api_env} is required for provider {provider}.", err=True)
        raise typer.Exit(code=2)


@cli.command("enhance-text")
def cmd_enhance_text(
    text: str = typer.Argument(..., help="Text to enhance"),
    instructions: Optional[str] = typer.Option(
        None, "--instructions", "-i", help="Custom rewriting instructions"
    ),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Override LLM model"),
) -> None:
    """Call enhance_text and display JSON response."""

    _require_llm_env()

    async def _run() -> None:
        result = await enhance_text(text=text, instructions=instructions, model=model)
        typer.echo(result)

    asyncio.run(_run())


@cli.command("enhance-message")
def cmd_enhance_message(
    source_id: int = typer.Argument(..., help="echo_messages.id to enhance"),
    instructions: Optional[str] = typer.Option(None, "--instructions", "-i"),
    model: Optional[str] = typer.Option(None, "--model", "-m"),
) -> None:
    """Enhance a DB message and store the output."""

    _require_llm_env()

    async def _run() -> None:
        result = await enhance_message_and_store(source_id=source_id, instructions=instructions, model=model)
        typer.echo(result)

    asyncio.run(_run())


@cli.command("list-enhanced")
def cmd_list_enhanced(
    source_id: int = typer.Argument(..., help="echo_messages.id to inspect"),
    limit: int = typer.Option(10, "--limit", "-l", help="Number of rows to return"),
) -> None:
    """List stored enhanced variants for a specific source message."""

    async def _run() -> None:
        result = await list_enhanced_for_message(source_id=source_id, limit=limit)
        typer.echo(result)

    asyncio.run(_run())


@cli.command("enhance-recent")
def cmd_enhance_recent(
    limit: int = typer.Option(5, "--limit", "-l", help="How many recent rows to fetch"),
    style: Optional[str] = typer.Option(None, "--style", "-s", help="Custom instructions"),
    model: Optional[str] = typer.Option(None, "--model", "-m"),
) -> None:
    """Summarize recent echo_messages with an LLM."""

    _require_llm_env()

    async def _run() -> None:
        result = await enhance_recent_messages(limit=limit, style=style, model=model)
        typer.echo(result)

    asyncio.run(_run())


if __name__ == "__main__":
    cli()
