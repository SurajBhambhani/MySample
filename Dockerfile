# syntax=docker/dockerfile:1.7-labs

# --- backend dependencies ---
FROM python:3.11-slim AS backend-deps
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /tmp/backend
COPY backend/requirements.txt ./requirements.txt
RUN pip install --upgrade pip \
    && pip install --no-cache-dir --prefix /install -r requirements.txt

# --- frontend build ---
FROM node:20-alpine AS frontend-build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
COPY frontend/tsconfig.json frontend/vite.config.ts ./
COPY frontend/index.html ./index.html
COPY frontend/src ./src
RUN corepack enable \
    && npm ci --no-audit --no-fund \
    && npm run build

# --- final runtime image ---
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=production \
    API_PORT=8000

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx supervisor \
    && rm -rf /var/lib/apt/lists/*

COPY --from=backend-deps /install /usr/local
COPY backend /app/backend
COPY --from=frontend-build /app/dist /app/frontend/dist
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

RUN adduser --disabled-password --gecos "" appuser \
    && chmod +x /app/backend/scripts/*.sh \
    && mkdir -p /var/log/supervisor \
    && chown -R appuser:appuser /app/backend

EXPOSE 80
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
