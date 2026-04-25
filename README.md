# NicheGPT

NicheGPT is a public-facing AI studio for building focused RAG workspaces, chatting with your own data, running MCP actions, and executing reusable agent workflows.

## Stack

- Backend: FastAPI + SQLAlchemy + Postgres/pgvector + SSE
- Frontend: React + TypeScript + Vite
- Auth: OAuth (Google/GitHub) with JWT session tokens
- Infra: Docker Compose + Nginx reverse proxy

## Quick start

1. Copy `.env.example` to `.env` and adjust values.
2. Start infra:
   - `docker compose up -d postgres`
3. Backend:
   - `cd backend`
   - `python -m venv .venv && source .venv/bin/activate`
   - `pip install -r requirements.txt`
   - `uvicorn app:app --reload --port 8100`
4. Frontend:
   - `cd frontend`
   - `npm install`
   - `npm run dev`
5. Get a token:
   - Development quick token:
     - `curl -X POST "http://localhost:8100/api/v1/auth/dev-token?email=you@example.com&name=You"`
   - OAuth:
     - Start with `/api/v1/auth/oauth/google/start` or `/api/v1/auth/oauth/github/start`

## API surface

- Health: `/health`
- API: `/api/v1/*`
- Metrics: `/metrics`

## Structure

- `backend/` FastAPI app and services
- `frontend/` React app
- `infra/` docker/nginx/systemd artifacts
- `docs/` architecture, migration, and release docs
