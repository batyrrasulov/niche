CREATE EXTENSION IF NOT EXISTS vector;

-- Placeholder migration for pgvector-enabled retrieval foundations.
-- SQLAlchemy currently creates core tables during startup for local development.
-- Production rollout should move all schema operations into managed Alembic migrations.
