# Changelog

Format follows [Keep a Changelog](https://keepachangelog.com/). No release has been tagged yet and the repo has no commits; everything below is unreleased.

## [Unreleased]

### Added
- **Foundation:** FastAPI backend, Next.js frontend, Docker Compose (pgvector, backend, worker, frontend), CI workflow, pre-commit, Sonar config.
- **Data and auth:** SQLAlchemy models and initial Alembic migration; signed-cookie passwordless login with seeded `employee`, `manager` and `admin` demo users; JSON logs with request id.
- **Ingestion:** md/txt/pdf parsers, heading-aware token chunker with exact offsets, OpenAI and fake embedders, DB-queue worker with transactional chunk swap, upload/list/delete/content/chunk endpoints, re-upload handling.
- **Retrieval:** access-filtered vector and full-text search, RRF hybrid, similarity gate, `POST /api/retrieve`.
- **Answering:** SSE chat with prompt v1, citation validation, grounding checks, no-answer gate, ticket-offer tool, ACL-scoped exact answer cache, model fallback, circuit breaker, budgets, single-flight, tickets API.
- **Audit and admin:** `llm_calls` and `audit_events` recording; `/api/admin` stats, request list/detail and audit events.
- **Frontend:** login, chat with citations and source drawer, upload status table, tickets, admin dashboard, SSE parser.
- **Security:** CSRF header on state-changing routes, per-user rate limits (chat and upload), log-only injection flagger, canary leakage and injection test suites.
- **Evaluation:** 20-question set and harness (`backend/eval`); results in `docs/eval.md` (fake embedder and fake LLM only).
- **Ship (Phase 9):** README, ARCHITECTURE, AI_LOG, SECURITY, threat model, runbook, cheatsheet, ADRs 001–008, CONTRIBUTING, `docker-compose.prod.yml`, `Caddyfile`, Dependabot config, `RATE_LIMIT_UPLOAD_PER_MINUTE` and production variables in `.env.example`.

### Fixed
- Employee re-upload could downgrade a manager-only document to `all` (now 403).
- Answer cache never fired because history was loaded after saving the current turn.
- Grounding number regex failed open on values followed by a unit (for example "11pm").
- `tsv` generated column rejected an explicit `NULL` on insert.
- Postgres enums stored Python member names instead of values.

### Known gaps
See "Known limitations" in the README. Notably: eval not run with real models, demo auth, no deployment yet, several playbook §5.12 failure-mode items not built (docs/runbook.md §11).
