# Phase 0-1 — Foundation + data layer & auth

**What I built:** The backend skeleton: typed `Settings` (every env var from
`.env.example`), a sync SQLAlchemy engine/session, every table from the
playbook's data model (§4) as one readable `models.py`, the first Alembic
migration (pgvector extension, enums, HNSW + GIN indexes, generated `tsv`
column), signed-cookie demo auth (`require_user`/`require_role`/
`allowed_access_levels`), JSON request-id logging, `/health` + `/ready`,
the `/api/auth/*` routes, an idempotent user seed, and compose/Dockerfile
plumbing. A worker container stub exists so `docker compose up` won't crash
before Phase 2 adds the real ingestion loop.

**Why this shape:** one flat `app` package (not `src/`), sync sessions, and
one `models.py` so the owner can see and change the whole schema without
async or layout indirection to fight through first.

**What I verified for real, not just by reading the code:** ran the
migration against a live `pgvector/pgvector:pg16` container, confirmed the
generated `tsv` column and HNSW index exist, downgraded and re-upgraded
cleanly, ran the seed twice (idempotent, no duplicates), and hit the running
app with curl: `/health`, `/ready`, login/me/logout for all three roles,
401 on no cookie, 401 on a tampered cookie, and 401 on an unknown email.

**Two real bugs this caught (not hypothetical):**
1. SQLAlchemy's `Enum` column type stores the Python `.name` ("EMPLOYEE") by
   default, not `.value` ("employee") — it inserted fine syntactically but
   failed against the real Postgres enum type. Fixed with a `pg_enum()`
   helper that sets `values_callable`.
2. Pydantic's `EmailStr` rejects `.local` as a reserved/special-use TLD, which
   broke login for the seeded `@demo.local` accounts the playbook specifies.
   Switched `LoginRequest.email` to a plain, regex-checked `str`.

**Left unfinished (expected — later phases):** ingestion/retrieval/LLM
packages are empty `__init__.py` stubs only; `frontend/Dockerfile` does not
exist yet, so the `frontend` service in `docker-compose.yml` will fail to
build until Phase 6; no documents/chat/tickets/admin routers yet.
