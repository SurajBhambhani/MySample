#!/usr/bin/env sh
set -e

if [ -z "${DATABASE_URL:-}" ]; then
    echo "[prod.sh] DATABASE_URL not set; skipping migrations" >&2
else
    echo "[prod.sh] Running Alembic migrations" >&2
    if ! alembic upgrade head; then
        echo "[prod.sh] WARNING: Alembic migrations failed; continuing without DB updates" >&2
    fi
fi

exec gunicorn app.main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:${API_PORT:-8000} --workers ${WEB_CONCURRENCY:-2} --timeout ${WEB_TIMEOUT:-60}
