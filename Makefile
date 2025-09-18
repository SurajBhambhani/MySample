SHELL := /bin/bash
PYTHON_BIN ?= python3
.ONESHELL:

.PHONY: help setup setup-mcp env-check migrate run-backend run-frontend run-mcp test clean-venv clean-venv-mcp pg-start-macos pg-stop-macos pg-status-macos pg-init pg-connect

help:
	@echo "Targets:"
	@echo "  setup        Create .venv and install backend deps"
	@echo "  setup-mcp    Create .venv-mcp and install MCP server deps"
	@echo "  env-check    Show key env values from .env (create from .env.example if missing)"
	@echo "  migrate      Run Alembic migrations (uses .env DATABASE_URL)"
	@echo "  run-backend  Start FastAPI with reload (uses .env)"
	@echo "  run-frontend Start Vite dev server"
	@echo "  run-mcp      Start MCP server (uses .env + LLM envs)"
	@echo "  test         Run backend tests"
	@echo "  clean-venv   Remove .venv"
	@echo "  clean-venv-mcp Remove .venv-mcp"
	@echo "  pg-start-macos  Start PostgreSQL via Homebrew services"
	@echo "  pg-stop-macos   Stop PostgreSQL via Homebrew services"
	@echo "  pg-status-macos Show Homebrew service status for PostgreSQL"
	@echo "  pg-init         Create local DB user/db (app/app, app_db)"
	@echo "  pg-connect      Connect to DB with psql"

setup:
	$(PYTHON_BIN) -m venv .venv
	.venv/bin/python -m pip install --upgrade pip
	.venv/bin/pip install -r backend/requirements.txt
	@echo "\nBackend setup complete. Activate: source .venv/bin/activate"

setup-mcp:
	$(PYTHON_BIN) -m venv .venv-mcp
	.venv-mcp/bin/python -m pip install --upgrade pip
	.venv-mcp/bin/pip install -r mcp-server/requirements.txt
	@echo "\nMCP setup complete. Activate: source .venv-mcp/bin/activate"

env-check:
	@if [ ! -f .env ]; then cp .env.example .env; echo "Created .env from .env.example"; fi
	@echo "\nEnvironment summary (from .env):"
	@grep -E '^(API_HOST|API_PORT|DATABASE_URL|VITE_PORT|CORS_ORIGINS)=' .env || true

migrate:
	set -a; source .env; set +a; \
	cd backend && ../.venv/bin/alembic -c alembic.ini upgrade head

run-backend:
	set -a; source .env; set +a; \
	.venv/bin/uvicorn app.main:app --app-dir backend --host $${API_HOST:-0.0.0.0} --port $${API_PORT:-8000} --reload

run-frontend:
	cd frontend && npm ci && npm run dev -- --host

run-mcp:
	set -a; source .env; set +a; \
	.venv-mcp/bin/python -m mcp_server.server

test:
	.venv/bin/pytest -q backend/tests

clean-venv:
	rm -rf .venv

clean-venv-mcp:
	rm -rf .venv-mcp

# --- macOS + Homebrew PostgreSQL helpers ---
pg-start-macos:
	@if brew list --versions postgresql@16 >/dev/null 2>&1; then \
		brew services start postgresql@16; \
	else \
		brew services start postgresql; \
	fi
	@echo "PostgreSQL service started (Homebrew)."

pg-stop-macos:
	@if brew list --versions postgresql@16 >/dev/null 2>&1; then \
		brew services stop postgresql@16; \
	else \
		brew services stop postgresql; \
	fi
	@echo "PostgreSQL service stopped (Homebrew)."

pg-status-macos:
	brew services list | egrep 'postgresql(@[0-9]+)?' || true

pg-init:
	# Create role and database if they don't exist (idempotent best-effort)
	-createuser app
	-psql -d postgres -c "ALTER USER app WITH PASSWORD 'app';"
	-createdb -O app app_db
	@echo "Initialized user 'app' and database 'app_db'."

pg-connect:
	psql "postgresql://app:app@localhost:5432/app_db"
