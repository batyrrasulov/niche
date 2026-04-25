# Niche

Niche is an agentic AI studio for workspace-grounded chat, MCP tool execution, and reusable workflow runtime in a terminal-first interface.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Repository and Deployment Mapping](#repository-and-deployment-mapping)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Local Setup](#local-setup)
- [Environment Variables](#environment-variables)
- [End-to-End Usage Flow](#end-to-end-usage-flow)
- [Verification Checklist](#verification-checklist)
- [Troubleshooting](#troubleshooting)

## Overview

Niche supports:

- Authenticated user sessions via OAuth or development tokens.
- Workspace and thread management for persistent conversation context.
- Source ingestion for retrieval-grounded answers.
- MCP connection discovery and tool invocation.
- Skills catalog and workflow execution endpoints.
- Server-sent event streaming for live orchestration feedback.

## Architecture

Core runtime flow:

1. User authenticates and selects a workspace/thread.
2. User prompt enters orchestration pipeline in `server/routes/threads.py`.
3. Pipeline runs staged execution:
   - Retrieval stage (workspace sources)
   - Optional web stage
   - Optional MCP stage
   - Synthesis stage
4. Backend streams `tool_event`, `token`, and `final` SSE events.
5. Frontend renders events in the terminal panel and runtime sidebars.

## Repository and Deployment Mapping

- Personal GitHub publish target for this branch history is [`batyrrasulov/niche`](https://github.com/batyrrasulov/niche).
- Production-style infra naming now uses `niche` identifiers (`/opt/niche`, `/var/www/niche`, `niche-api.service`, `niche.conf`).

## Tech Stack

- Server: FastAPI, SQLAlchemy, Pydantic, SSE
- Client: React, TypeScript, Vite
- Data: SQLite by default, Postgres/pgvector via Docker Compose
- Auth: OAuth (Google/GitHub) + JWT
- Infra: Docker Compose, Nginx, systemd

## Project Structure

- `server/` API routes, models, services, and worker stubs
- `src/` terminal-first UI and API client
- `system/` local compose and production deployment artifacts

## Local Setup

### 1) Copy environment template

```bash
cp .env.example .env
```

### 2) Start dependencies

```bash
docker compose -f system/docker-compose.yml up -d postgres
```

If Docker is not running, the server can still run against local SQLite defaults.

### 3) Start server

```bash
cd server
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload --port 8100
```

### 4) Start client

```bash
cd src
npm install
npm run dev
```

Frontend URL: `http://localhost:5173`  
Server health: `http://127.0.0.1:8100/health`

### 5) Acquire a token

Development token:

```bash
curl -X POST "http://localhost:8100/api/v1/auth/dev-token?email=you@example.com&name=You"
```

OAuth start endpoints:

- `/api/v1/auth/oauth/google/start`
- `/api/v1/auth/oauth/github/start`

## Environment Variables

Canonical variables:

- `NICHE_ENV`
- `NICHE_API_PORT`
- `NICHE_FRONTEND_ORIGIN`
- `NICHE_DATABASE_URL`
- `NICHE_JWT_SECRET`
- `NICHE_JWT_EXPIRES_MINUTES`
- `NICHE_GOOGLE_CLIENT_ID`
- `NICHE_GOOGLE_CLIENT_SECRET`
- `NICHE_GITHUB_CLIENT_ID`
- `NICHE_GITHUB_CLIENT_SECRET`
- `NICHE_OAUTH_REDIRECT_BASE`
- `NICHE_RATE_LIMIT_PER_MINUTE`

Compatibility:

- Frontend uses `niche-token` for session storage.

## End-to-End Usage Flow

1. Save a bearer token in the UI.
2. Create a workspace and thread.
3. Add at least one source (`text` or `url`).
4. Add an MCP connection and run tool discovery.
5. Install at least one skill from catalog.
6. Create and run a workflow.
7. Send a chat request and watch orchestration stream in terminal:
   - retrieval
   - web search
   - MCP action
   - synthesis

## Verification Checklist

Use this sequence after major changes:

```bash
# client
cd src && npm run build

# server syntax
cd ../server && source .venv/bin/activate && python -m compileall .

# server health
curl http://127.0.0.1:8100/health
```

Integration smoke should validate:

- auth token creation
- workspace/thread lifecycle
- source ingestion
- MCP discover + invoke
- skill install
- workflow run
- chat SSE (`tool_event`, `token`, `final`)

## Troubleshooting

### Server not reachable on `8100`

- Ensure the server process is running with `uvicorn`.
- Check `.env` for invalid DB URL.
- If Docker is down and Postgres URL is configured, switch to SQLite or start Docker.

### Client not reachable on `5173`

- Restart `npm run dev` in `src/`.
- Confirm no port conflict.
- Access via `http://localhost:5173` (hostname), not strict `127.0.0.1`, if local resolver settings differ.

### MCP discover/invoke fails

- Verify MCP server URL and token.
- Confirm server exposes `/tools` and `/invoke` endpoints expected by `services_mcp.py`.
- Re-run discover before invoke when `tools_json` is empty.
