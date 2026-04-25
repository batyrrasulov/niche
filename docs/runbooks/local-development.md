# Local Development Runbook

## Prerequisites

- Python 3.11+
- Node.js 20+
- Docker

## Start dependencies

```bash
docker compose -f infra/docker-compose.yml up -d postgres
```

## Start backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload --port 8100
```

## Start frontend

```bash
cd frontend
npm install
npm run dev
```

