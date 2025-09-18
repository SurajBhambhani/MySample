#!/usr/bin/env bash
set -euo pipefail

# Simple helper to invoke the MCP enrichment CLI with the current virtualenv.
# Usage examples:
#   scripts/enrich_with_mcp.sh "Please enhance this text"
#   scripts/enrich_with_mcp.sh --instructions "Rewrite for release notes" "Bug fixed" 
#
# Requirements:
#   1) .venv-mcp must exist (run: make setup-mcp PYTHON_BIN=/opt/homebrew/opt/python@3.11/bin/python3.11)
#   2) DATABASE_URL must be set (source .env)
#   3) LLM env vars must be set (e.g., LLM_PROVIDER=ollama)

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${REPO_ROOT}/.venv-mcp"
PYTHON_BIN="${VENV_DIR}/bin/python"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Missing ${PYTHON_BIN}. Run 'make setup-mcp PYTHON_BIN=/opt/homebrew/opt/python@3.11/bin/python3.11' first." >&2
  exit 1
fi

if [[ "${DATABASE_URL:-}" == "" ]]; then
  echo "DATABASE_URL is not set. Source your .env (e.g., 'set -a; source .env; set +a')." >&2
  exit 1
fi

if [[ "${LLM_PROVIDER:-}" == "" ]]; then
  echo "LLM_PROVIDER is not set. Export LLM_PROVIDER and related API keys (or set to 'ollama')." >&2
  exit 1
fi

PYTHONPATH="${REPO_ROOT}/mcp-server${PYTHONPATH:+:${PYTHONPATH}}" \
  "${PYTHON_BIN}" "${REPO_ROOT}/mcp-server/scripts/mcp_cli.py" enhance-text "$@"
