# MCP Relay

MCP Relay is a production-ready starter that combines a FastAPI backend, a React (Vite + TypeScript) frontend, and a PostgreSQL database, with Docker support for development and production.

## Tech Stack
- Backend: FastAPI, SQLAlchemy, Alembic, Pydantic Settings, Uvicorn/Gunicorn
- Frontend: React, Vite, TypeScript, Axios
- Database: PostgreSQL
- Infrastructure: Docker, docker-compose, Nginx
- CI: GitHub Actions

## Repo Structure
- `backend/` – FastAPI app, SQLAlchemy models, Alembic, tests, Dockerfile
- `frontend/` – Vite + React + TypeScript app, Axios wrapper, Dockerfile, Nginx config
- `infra/` – docker-compose for dev and prod
- `.github/workflows/ci.yml` – CI pipeline for tests and image builds
- `.env.example` – Example environment variables
- `mcp-server/` – Python MCP server exposing health, echo, DB, and infra tools

# MCP Relay

MCP Relay is a production-ready starter that combines a FastAPI backend, a React (Vite + TypeScript) frontend, and a PostgreSQL database, with Docker support for development and production.

## Tech Stack
- Backend: FastAPI, SQLAlchemy, Alembic, Pydantic Settings, Uvicorn/Gunicorn
- Frontend: React, Vite, TypeScript, Axios
- Database: PostgreSQL
- Infrastructure: Docker, docker-compose, Nginx
- CI: GitHub Actions

## Repo Structure
- `backend/` – FastAPI app, SQLAlchemy models, Alembic, tests, Dockerfile
- `frontend/` – Vite + React + TypeScript app, Axios wrapper, Dockerfile, Nginx config
- `infra/` – docker-compose for dev and prod
- `.github/workflows/ci.yml` – CI pipeline for tests and image builds
- `.env.example` – Example environment variables
- `mcp-server/` – Python MCP server exposing health, echo, DB, and infra tools

## Architecture

This project follows a classic three-tier architecture, augmented with a Management and Control Plane (MCP) server, and containerized with Docker for consistent development and production environments.

```mermaid
graph TD
    subgraph "User Interface"
        A[Browser / Client Application]
    end

    subgraph "Web Tier"
        B(Web Server / Frontend Service)
    end

    subgraph "Application Tier"
        C(Backend API Service)
    end

    subgraph "Data Tier"
        D(PostgreSQL Database)
    end

    subgraph "Management & Tools"
        E(MCP Server)
    end

    A -- "HTTP/S Requests" --> B
    B -- "API Calls (e.g., /api/data)" --> C
    C -- "Database Queries" --> D

    E -- "Health Checks / DB Tools" --> C
    E -- "DB Access" --> D
    E -- "LLM Services" --> F[External LLM Provider]

    style A fill:#ADD8E6,stroke:#333,stroke-width:2px
    style B fill:#90EE90,stroke:#333,stroke-width:2px
    style C fill:#FFD700,stroke:#333,stroke-width:2px
    style D fill:#FFB6C1,stroke:#333,stroke-width:2px
    style E fill:#DDA0DD,stroke:#333,stroke-width:2px
    style F fill:#C0C0C0,stroke:#333,stroke-width:2px
```

-   **Frontend:** A React application built with Vite.
    -   In development, the Vite dev server provides hot module replacement and proxies API requests to the backend.
    -   In production, the React app is built into static files and served by Nginx.
-   **Backend:** A Python-based API built with FastAPI.
    -   It handles business logic and communicates with the PostgreSQL database.
    -   In development, it's run with Uvicorn for live reloading.
    -   In production, it's run with Gunicorn and Uvicorn workers for performance and scalability.
-   **Database:** A PostgreSQL database for data persistence.
-   **Web Server:**
    -   In development, the Vite dev server is used.
    -   In production, Nginx serves the static frontend files and acts as a reverse proxy for the backend API.
-   **MCP Server:** A separate Python server that provides a set of tools for interacting with the project, including health checks, database operations, and integration with external LLM providers.

This setup ensures that the development environment closely mirrors the production environment, reducing the risk of "it works on my machine" issues.

## Sequence Diagram

This sequence diagram illustrates a typical data fetching operation within the application.

```mermaid
sequenceDiagram
    participant Browser
    participant Frontend
    participant Backend
    participant Database

    Browser->>Frontend: User requests data
    Frontend->>Backend: GET /api/data
    Backend->>Database: SELECT * FROM items
    Database-->>Backend: Rows of data
    Backend-->>Frontend: JSON data
    Frontend->>Browser: Display data
```

## Quickstart
1. Copy `.env.example` to `.env` and adjust if needed (optional for local Docker compose; files already refer to `.env.example`).

### Run in Development
From the project root:

- Start services:
  - `docker compose -f infra/docker-compose.dev.yml up --build`
- Services:
  - Postgres at `localhost:5432`
  - Backend (FastAPI + reload) at `http://localhost:8000`
  - Frontend (Vite dev server with proxy) at `http://localhost:5173`
- Dev proxy: Vite proxies `/api` and `/healthz` to the backend container, so frontend calls `fetch('/api/...')` work in dev.

Apply DB migrations automatically on container start. To run manually inside the backend container:
- `docker compose -f infra/docker-compose.dev.yml exec backend alembic upgrade head`

### Run in Production
- Build and run optimized images:
  - `docker compose -f infra/docker-compose.prod.yml up --build -d`
- Services:
  - Frontend (Nginx serving static + proxy to backend) at `http://localhost:8080`
  - Backend (Gunicorn + Uvicorn workers) internal at `backend:8000`
  - Postgres internal at `db:5432`

Migrations run on container start via `backend/scripts/prod.sh`.

### Backend Endpoints
- `GET /healthz` → `{ "status": "ok" }`
- `POST /api/echo` with JSON `{ "message": "..." }` → `{ "message": "...", "length": n }`

### Running Backend Tests
- Locally (with Python installed):
  - `pip install -r backend/requirements.txt`
  - `pytest -q backend/tests`
- In CI: see `.github/workflows/ci.yml` (tests run without requiring a DB).

### Alembic Migrations
- Generate a new migration after changing models:
  - `docker compose -f infra/docker-compose.dev.yml exec backend alembic revision -m "your message" --autogenerate`
- Apply migrations:
  - `docker compose -f infra/docker-compose.dev.yml exec backend alembic upgrade head`
 - New table for enhanced messages is added in migration `0002_add_enhanced_table`.

### Environment Variables
See `.env.example`. Key variables:
- `DATABASE_URL` – SQLAlchemy database URL
- `API_HOST`, `API_PORT` – Backend bind address/port
- `CORS_ORIGINS` – `*` or comma-separated list
- `VITE_API_BASE_URL` – Optional override; leave empty for same-origin (prod) and dev proxy

### Run Locally on macOS (without Docker)

These instructions assume you are using [Homebrew](https://brew.sh/) for package management.

#### 1. Database (PostgreSQL)

1.  **Install and start PostgreSQL:**

    ```sh
    brew install postgresql
    brew services start postgresql
    ```

2.  **Create the database and user:**

    The default credentials in `.env.example` are `app` / `app` for user and password, and `app_db` for the database.

    ```sh
    psql postgres -c "CREATE DATABASE app_db;"
    psql postgres -c "CREATE USER app WITH PASSWORD 'app';"
    psql postgres -c "GRANT ALL PRIVILEGES ON DATABASE app_db TO app;"
    ```

#### 2. Backend (Python/FastAPI)

1.  **Navigate to the backend directory:**

    ```sh
    cd backend
    ```

2.  **Create a virtual environment and install dependencies:**

    ```sh
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

3.  **Set the database URL environment variable:**

    The backend needs to connect to the local PostgreSQL instance, not the Docker one.

    ```sh
    export DATABASE_URL=postgresql+psycopg2://app:app@localhost:5432/app_db
    ```

4.  **Apply database migrations:**

    ```sh
    alembic upgrade head
    ```

5.  **Run the backend server:**

    ```sh
    uvicorn app.main:app --reload
    ```

    The backend will be available at `http://localhost:8000`.

#### 3. Frontend (React/Vite)

1.  **Navigate to the frontend directory:**

    In a new terminal window:

    ```sh
    cd frontend
    ```

2.  **Install dependencies and run the dev server:**

    ```sh
    npm install
    npm run dev
    ```

    The frontend will be available at `http://localhost:5173`. It is configured to proxy API requests to the backend at `http://localhost:8000`.

## CI/CD
- On push/PR, GitHub Actions:
  - Installs backend dependencies and runs pytest
  - Builds Docker images for backend and frontend (prod targets)
- Optional GHCR push steps are included but commented out.

## Notes
- In dev, the frontend dev server proxies API requests to the backend container; in prod, Nginx inside the frontend image serves the built app and proxies `/api` to the backend service.
- MCP Relay includes an `echo_messages` table and Alembic migration as a template; the app doesn’t persist echoes by default to keep the starter simple.

## MCP Server (Python)
This repo includes a Python MCP server that exposes:
- Tools: `health`, `echo`, `db_query` (SELECT-only), `db_insert_echo`, `alembic_upgrade`, `compose_up_dev`, `compose_down_dev`, `compose_logs_dev`, `compose_up_prod`, `compose_down_prod`.
  - LLM tools: `enhance_text`, `enhance_recent_messages`
  - Persistence tools: `enhance_message_and_store`, `list_enhanced_for_message`

### Run MCP Server (locally)
- Prereqs: Python 3.11+
- Install deps: `pip install -r mcp-server/requirements.txt`
- Set env (at minimum): `DATABASE_URL` (e.g., `postgresql+psycopg2://app:app@localhost:5432/app_db`)
- Run: `python -m mcp_server.server`

Environment variables:
- `DATABASE_URL` – required for DB tools
- `BACKEND_URL` – defaults to `http://localhost:8000` for `health`
- `BACKEND_DIR` – path to `backend/` for Alembic (defaults to `<repo>/backend` when run in repo root)
- `LLM_PROVIDER` – one of `openai`, `anthropic`, `openrouter`, `azure_openai`, `ollama` (default: `openai`)
 - `LLM_MODEL` – default model (e.g., `gpt-4o-mini`, `claude-3-5-sonnet-20240620`)
 - For OpenAI: `OPENAI_API_KEY`
 - For Anthropic: `ANTHROPIC_API_KEY`
- For OpenRouter: `OPENROUTER_API_KEY`
- For Azure OpenAI: `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`, optional `AZURE_OPENAI_API_VERSION`
- For Ollama (local LLM):
  - Install and run [Ollama](https://ollama.com/) locally (`brew install ollama`, `ollama serve`)
  - Pull a model (e.g., `ollama pull llama3`)
  - Optional envs: `OLLAMA_ENDPOINT` (default `http://localhost:11434`), `OLLAMA_MODEL` (default `llama3`), `OLLAMA_OPTIONS` (JSON for generation options)

### Example client configuration (Claude Desktop)
Add to your Claude Desktop `mcp.json`:

```
{
  "mcpServers": {
    "mcp-relay": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "env": {
        "DATABASE_URL": "postgresql+psycopg2://app:app@localhost:5432/app_db",
        "BACKEND_URL": "http://localhost:8000",
        "BACKEND_DIR": "/absolute/path/to/repo/backend"
      },
      "cwd": "/absolute/path/to/repo"
    }
  }
}
```

### Run MCP Server (container)
Build and run (note: MCP via stdio in a container requires appropriate stdio wiring by the client):
- `docker build -t mcp-relay -f mcp-server/Dockerfile .`
- `docker run --rm -e DATABASE_URL=... mcp-relay`

### Examples
- Enhance arbitrary text: call tool `enhance_text` with `{ "text": "raw message..." }`.
- Enhance last 5 DB messages: call tool `enhance_recent_messages` with `{ "limit": 5 }`.
- Enhance one DB message and store: `enhance_message_and_store` with `{ "source_id": 42 }`.
- List stored enhancements for a message: `list_enhanced_for_message` with `{ "source_id": 42 }`

### CLI shortcut for local testing
- Ensure `.venv-mcp` is set up: `make setup-mcp PYTHON_BIN=/opt/homebrew/opt/python@3.11/bin/python3.11`
- Set env vars (`LLM_PROVIDER`, API keys, `DATABASE_URL`)
- For local Ollama: `export LLM_PROVIDER=ollama` (and optionally `OLLAMA_MODEL=llama3.1`, etc.)
- Run CLI commands, e.g.:
  - `scripts/enrich_with_mcp.sh "Some raw content"`
  - `PYTHONPATH=mcp-server .venv-mcp/bin/python mcp-server/scripts/mcp_cli.py enhance-message 42`

## Quickstart
1. Copy `.env.example` to `.env` and adjust if needed (optional for local Docker compose; files already refer to `.env.example`).

### Run in Development
From the project root:

- Start services:
  - `docker compose -f infra/docker-compose.dev.yml up --build`
- Services:
  - Postgres at `localhost:5432`
  - Backend (FastAPI + reload) at `http://localhost:8000`
  - Frontend (Vite dev server with proxy) at `http://localhost:5173`
- Dev proxy: Vite proxies `/api` and `/healthz` to the backend container, so frontend calls `fetch('/api/...')` work in dev.

Apply DB migrations automatically on container start. To run manually inside the backend container:
- `docker compose -f infra/docker-compose.dev.yml exec backend alembic upgrade head`

### Run in Production
- Build and run optimized images:
  - `docker compose -f infra/docker-compose.prod.yml up --build -d`
- Services:
  - Frontend (Nginx serving static + proxy to backend) at `http://localhost:8080`
  - Backend (Gunicorn + Uvicorn workers) internal at `backend:8000`
  - Postgres internal at `db:5432`

Migrations run on container start via `backend/scripts/prod.sh`.

### Backend Endpoints
- `GET /healthz` → `{ "status": "ok" }`
- `POST /api/echo` with JSON `{ "message": "..." }` → `{ "message": "...", "length": n }`

### Running Backend Tests
- Locally (with Python installed):
  - `pip install -r backend/requirements.txt`
  - `pytest -q backend/tests`
- In CI: see `.github/workflows/ci.yml` (tests run without requiring a DB).

### Alembic Migrations
- Generate a new migration after changing models:
  - `docker compose -f infra/docker-compose.dev.yml exec backend alembic revision -m "your message" --autogenerate`
- Apply migrations:
  - `docker compose -f infra/docker-compose.dev.yml exec backend alembic upgrade head`
 - New table for enhanced messages is added in migration `0002_add_enhanced_table`.

### Environment Variables
See `.env.example`. Key variables:
- `DATABASE_URL` – SQLAlchemy database URL
- `API_HOST`, `API_PORT` – Backend bind address/port
- `CORS_ORIGINS` – `*` or comma-separated list
- `VITE_API_BASE_URL` – Optional override; leave empty for same-origin (prod) and dev proxy

### Run Locally on macOS (without Docker)

These instructions assume you are using [Homebrew](https://brew.sh/) for package management.

#### 1. Database (PostgreSQL)

1.  **Install and start PostgreSQL:**

    ```sh
    brew install postgresql
    brew services start postgresql
    ```

2.  **Create the database and user:**

    The default credentials in `.env.example` are `app` / `app` for user and password, and `app_db` for the database.

    ```sh
    psql postgres -c "CREATE DATABASE app_db;"
    psql postgres -c "CREATE USER app WITH PASSWORD 'app';"
    psql postgres -c "GRANT ALL PRIVILEGES ON DATABASE app_db TO app;"
    ```

#### 2. Backend (Python/FastAPI)

1.  **Navigate to the backend directory:**

    ```sh
    cd backend
    ```

2.  **Create a virtual environment and install dependencies:**

    ```sh
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

3.  **Set the database URL environment variable:**

    The backend needs to connect to the local PostgreSQL instance, not the Docker one.

    ```sh
    export DATABASE_URL=postgresql+psycopg2://app:app@localhost:5432/app_db
    ```

4.  **Apply database migrations:**

    ```sh
    alembic upgrade head
    ```

5.  **Run the backend server:**

    ```sh
    uvicorn app.main:app --reload
    ```

    The backend will be available at `http://localhost:8000`.

#### 3. Frontend (React/Vite)

1.  **Navigate to the frontend directory:**

    In a new terminal window:

    ```sh
    cd frontend
    ```

2.  **Install dependencies and run the dev server:**

    ```sh
    npm install
    npm run dev
    ```

    The frontend will be available at `http://localhost:5173`. It is configured to proxy API requests to the backend at `http://localhost:8000`.

## CI/CD
- On push/PR, GitHub Actions:
  - Installs backend dependencies and runs pytest
  - Builds Docker images for backend and frontend (prod targets)
- Optional GHCR push steps are included but commented out.

## Notes
- In dev, the frontend dev server proxies API requests to the backend container; in prod, Nginx inside the frontend image serves the built app and proxies `/api` to the backend service.
- MCP Relay includes an `echo_messages` table and Alembic migration as a template; the app doesn’t persist echoes by default to keep the starter simple.

## MCP Server (Python)
This repo includes a Python MCP server that exposes:
- Tools: `health`, `echo`, `db_query` (SELECT-only), `db_insert_echo`, `alembic_upgrade`, `compose_up_dev`, `compose_down_dev`, `compose_logs_dev`, `compose_up_prod`, `compose_down_prod`.
  - LLM tools: `enhance_text`, `enhance_recent_messages`
  - Persistence tools: `enhance_message_and_store`, `list_enhanced_for_message`

### Run MCP Server (locally)
- Prereqs: Python 3.11+
- Install deps: `pip install -r mcp-server/requirements.txt`
- Set env (at minimum): `DATABASE_URL` (e.g., `postgresql+psycopg2://app:app@localhost:5432/app_db`)
- Run: `python -m mcp_server.server`

Environment variables:
- `DATABASE_URL` – required for DB tools
- `BACKEND_URL` – defaults to `http://localhost:8000` for `health`
- `BACKEND_DIR` – path to `backend/` for Alembic (defaults to `<repo>/backend` when run in repo root)
- `LLM_PROVIDER` – one of `openai`, `anthropic`, `openrouter`, `azure_openai`, `ollama` (default: `openai`)
 - `LLM_MODEL` – default model (e.g., `gpt-4o-mini`, `claude-3-5-sonnet-20240620`)
 - For OpenAI: `OPENAI_API_KEY`
 - For Anthropic: `ANTHROPIC_API_KEY`
- For OpenRouter: `OPENROUTER_API_KEY`
- For Azure OpenAI: `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`, optional `AZURE_OPENAI_API_VERSION`
- For Ollama (local LLM):
  - Install and run [Ollama](https://ollama.com/) locally (`brew install ollama`, `ollama serve`)
  - Pull a model (e.g., `ollama pull llama3`)
  - Optional envs: `OLLAMA_ENDPOINT` (default `http://localhost:11434`), `OLLAMA_MODEL` (default `llama3`), `OLLAMA_OPTIONS` (JSON for generation options)

### Example client configuration (Claude Desktop)
Add to your Claude Desktop `mcp.json`:

```
{
  "mcpServers": {
    "mcp-relay": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "env": {
        "DATABASE_URL": "postgresql+psycopg2://app:app@localhost:5432/app_db",
        "BACKEND_URL": "http://localhost:8000",
        "BACKEND_DIR": "/absolute/path/to/repo/backend"
      },
      "cwd": "/absolute/path/to/repo"
    }
  }
}
```

### Run MCP Server (container)
Build and run (note: MCP via stdio in a container requires appropriate stdio wiring by the client):
- `docker build -t mcp-relay -f mcp-server/Dockerfile .`
- `docker run --rm -e DATABASE_URL=... mcp-relay`

### Examples
- Enhance arbitrary text: call tool `enhance_text` with `{ "text": "raw message..." }`.
- Enhance last 5 DB messages: call tool `enhance_recent_messages` with `{ "limit": 5 }`.
- Enhance one DB message and store: `enhance_message_and_store` with `{ "source_id": 42 }`.
- List stored enhancements for a message: `list_enhanced_for_message` with `{ "source_id": 42 }`.

### CLI shortcut for local testing
- Ensure `.venv-mcp` is set up: `make setup-mcp PYTHON_BIN=/opt/homebrew/opt/python@3.11/bin/python3.11`
- Set env vars (`LLM_PROVIDER`, API keys, `DATABASE_URL`)
- For local Ollama: `export LLM_PROVIDER=ollama` (and optionally `OLLAMA_MODEL=llama3.1`, etc.)
- Run CLI commands, e.g.:
  - `scripts/enrich_with_mcp.sh "Some raw content"`
  - `PYTHONPATH=mcp-server .venv-mcp/bin/python mcp-server/scripts/mcp_cli.py enhance-message 42`
