# syntax=docker/dockerfile:1.7-labs

FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY mcp-server/requirements.txt ./requirements.txt
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --upgrade pip \
    && pip install -r requirements.txt

COPY mcp-server/mcp_server ./mcp_server

# Default envs; override as needed
ENV BACKEND_URL=http://localhost:8000 \
    BACKEND_DIR=/app/backend \
    DATABASE_URL=

# Note: MCP servers typically communicate via stdio; running in a container
# requires mapping stdin/stdout appropriately. This container is provided for
# convenience; most clients will run `python -m mcp_server.server` directly.
CMD ["python", "-m", "mcp_server.server"]
