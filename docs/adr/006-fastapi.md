# ADR 006: Python 3.12 and FastAPI for the backend

**Status:** accepted

**Context.** The backend does document parsing (PDF), tokenisation, embeddings, LLM streaming and SQL. The frontend is Next.js, so the API could have been Node too.

**Decision.** FastAPI on Python 3.12 with Pydantic, SQLAlchemy 2.0 and Alembic, managed with `uv`; ruff and mypy for quality.

**Why.**
- The RAG ecosystem (pgvector bindings, `pypdf`, `tiktoken`, the `openai` SDK) is Python-first.
- Pydantic models give typed request/response validation and an OpenAPI schema for free.
- `sse-starlette` makes SSE straightforward.

**Consequences.**
- Two languages in one repo. The frontend talks to the backend only over `/api`, and `frontend/src/lib/types.ts` is kept in sync with `schemas.py` by hand (no generated client).
- Chat routes are synchronous generators; fine at demo scale, to be revisited under load.
- `/docs` is disabled when `APP_ENV=production`.
