#!/usr/bin/env bash
# One-stop helper for setting up and running the project with a local Ollama-backed MCP pipeline.
# Usage:
#   ./scripts/enrich_with_mcp.sh setup   # install deps, prepare env, run migrations
#   ./scripts/enrich_with_mcp.sh start   # launch Ollama (if needed), backend, and frontend
#   ./scripts/enrich_with_mcp.sh all     # run setup then start (default)
#   ./scripts/enrich_with_mcp.sh stop    # stop processes started by this script (if PID file exists)
#
# The script stores runtime PIDs under tmp/enrich_with_mcp.pids so it can cleanly stop services it started.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/tmp"
PID_FILE="$ROOT_DIR/tmp/enrich_with_mcp.pids"
mkdir -p "$LOG_DIR"

STARTED_PIDS=()
STARTED_NAMES=()
STEP_COUNTER=0

log() {
    printf '[%.19s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

step() {
    STEP_COUNTER=$((STEP_COUNTER + 1))
    log "Step ${STEP_COUNTER}: $*"
}

reset_step_counter() {
    STEP_COUNTER=0
}

fail() {
    log "ERROR: $*"
    exit 1
}

require_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        fail "Missing required command: $1"
    fi
}

ensure_homebrew_pkg() {
    local pkg="$1"
    if ! brew ls --versions "$pkg" >/dev/null 2>&1; then
        log "Installing Homebrew package: $pkg"
        HOMEBREW_NO_AUTO_UPDATE=1 brew install "$pkg"
    else
        log "Homebrew package already present: $pkg"
    fi
}

ensure_env_file() {
    cd "$ROOT_DIR"
    if [ ! -f .env ]; then
        if [ ! -f .env.example ]; then
            fail "Neither .env nor .env.example exists"
        fi
        cp .env.example .env
        log "Created .env from .env.example"
    fi
    python3 <<'PY'
from pathlib import Path

updates = {
    "LLM_PROVIDER": "ollama",
    "OLLAMA_ENDPOINT": "http://localhost:11434",
    "OLLAMA_MODEL": "llama3",
    "LLM_MODEL": "llama3",
}

path = Path('.env')
lines = path.read_text().splitlines()
for key, value in updates.items():
    for idx, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[idx] = f"{key}={value}"
            break
    else:
        lines.append(f"{key}={value}")
path.write_text('\n'.join(lines) + '\n')
PY
    log "Ensured Ollama-related environment variables in .env"
}

record_pid() {
    local name="$1" pid="$2"
    STARTED_NAMES+=("$name")
    STARTED_PIDS+=("$pid")
    printf '%s:%s\n' "$pid" "$name" >> "$PID_FILE"
}

start_process() {
    local name="$1"; shift
    local log_file="$LOG_DIR/${name}.log"
    log "Starting $name (logging to $log_file)"
    "$@" >"$log_file" 2>&1 &
    local pid=$!
    log "$name started with PID $pid"
    record_pid "$name" "$pid"
}

cleanup() {
    if [ ${#STARTED_PIDS[@]} -eq 0 ]; then
        return
    fi
    log "Stopping started processes"
    for i in "${!STARTED_PIDS[@]}"; do
        local pid="${STARTED_PIDS[$i]}"
        local name="${STARTED_NAMES[$i]}"
        if kill -0 "$pid" >/dev/null 2>&1; then
            log "Stopping $name (PID $pid)"
            kill "$pid" >/dev/null 2>&1 || true
            wait "$pid" >/dev/null 2>&1 || true
        fi
    done
    : > "$PID_FILE"
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

setup_phase() {
    cd "$ROOT_DIR"
    reset_step_counter

    step "Install/verify Homebrew packages (python@3.11, node, postgresql@16, ollama)"
    require_cmd brew
    ensure_homebrew_pkg python@3.11
    ensure_homebrew_pkg node
    ensure_homebrew_pkg postgresql@16
    ensure_homebrew_pkg ollama

    step "Sync .env with Ollama defaults"
    ensure_env_file

    step "Verify CLI prerequisites (python3, npm, make, ollama)"
    require_cmd python3
    require_cmd npm
    require_cmd make
    require_cmd ollama

    step "Install frontend dependencies (npm install)"
    npm --prefix frontend install

    step "Create/refresh Python virtual environment (make setup)"
    make setup

    step "Start PostgreSQL service (make pg-start-macos)"
    make pg-start-macos

    step "Ensure app database and schema (make pg-init && make migrate)"
    make pg-init
    make migrate

    step "Pull Ollama model llama3"
    ollama pull llama3

    log "Setup phase complete"
}

start_phase() {
    cd "$ROOT_DIR"
    reset_step_counter

    step "Start Ollama serve locally if not already running"
    if pgrep -f 'ollama serve' >/dev/null 2>&1; then
        log "Ollama serve already running; will not start a new instance"
    else
        start_process "ollama" ollama serve
    fi

    step "Launch FastAPI backend (make run-backend)"
    start_process "backend" bash -lc "cd '$ROOT_DIR' && make run-backend"

    step "Launch Vite frontend (npm run dev -- --host)"
    start_process "frontend" bash -lc "cd '$ROOT_DIR' && npm --prefix frontend run dev -- --host"

    log "All services started. Attach to logs under $LOG_DIR or press Ctrl+C to stop."
    wait
}

stop_phase() {
    reset_step_counter
    if [ ! -f "$PID_FILE" ]; then
        log "No PID file found; nothing to stop"
        return
    fi

    step "Stop processes recorded in $PID_FILE"
    while IFS= read -r line; do
        [ -z "$line" ] && continue
        pid="${line%%:*}"
        name="${line#*:}"
        if kill -0 "$pid" >/dev/null 2>&1; then
            log "Stopping $name (PID $pid)"
            kill "$pid" >/dev/null 2>&1 || true
            wait "$pid" >/dev/null 2>&1 || true
        fi
    done < "$PID_FILE"
    : > "$PID_FILE"
    log "Stopped processes recorded in $PID_FILE"
}

cmd="${1:-all}"
case "$cmd" in
    setup)
        setup_phase
        ;;
    start)
        : > "$PID_FILE"
        start_phase
        ;;
    all)
        setup_phase
        : > "$PID_FILE"
        start_phase
        ;;
    stop)
        stop_phase
        ;;
    *)
        cat <<'USAGE'
Usage: ./scripts/enrich_with_mcp.sh [setup|start|all|stop]
  setup  Install dependencies, prepare environment, run migrations
  start  Launch Ollama (if needed), backend, and frontend processes
  all    Run setup then start (default)
  stop   Stop processes recorded in tmp/enrich_with_mcp.pids
USAGE
        exit 1
        ;;
esac
