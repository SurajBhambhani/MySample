#!/usr/bin/env sh
set -e

alembic upgrade head
exec gunicorn app.main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:${API_PORT:-8000} --workers ${WEB_CONCURRENCY:-2} --timeout ${WEB_TIMEOUT:-60}
