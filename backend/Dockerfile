# syntax=docker/dockerfile:1.7-labs

FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
RUN adduser --disabled-password --gecos "" appuser

# Install runtime deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt


# --- dev stage ---
FROM base AS dev
ENV APP_ENV=development
COPY backend /app
RUN chmod +x scripts/dev.sh scripts/prod.sh
USER appuser
EXPOSE 8000
CMD ["/bin/sh", "-c", "./scripts/dev.sh"]


# --- prod stage ---
FROM base AS prod
ENV APP_ENV=production
COPY backend /app
RUN chmod +x scripts/dev.sh scripts/prod.sh \
    && adduser appuser --disabled-password --gecos "" || true
USER appuser
EXPOSE 8000
CMD ["/bin/sh", "-c", "./scripts/prod.sh"]

