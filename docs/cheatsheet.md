# Cheatsheet: to change X, edit Y, run Z

Run backend tests from `backend/` with `uv run pytest <path> -q`. Integration and security tests need a migrated Postgres and `TEST_DATABASE_URL` (see README). After any change run `make check`.

## Retrieval and answering

| Change | Edit | Run |
|---|---|---|
| **Chunk size / overlap** | `CHUNK_TARGET_TOKENS`, `CHUNK_OVERLAP_TOKENS` in `.env` (defaults in `backend/app/config.py`). Chunking logic: `backend/app/ingestion/chunker.py`. **Existing documents keep their old chunks**; re-upload changed files, or reset them to `queued` (runbook §7) to re-chunk. Re-chunking changes `text_hash`es, so embeddings are recomputed. | `uv run pytest tests/unit/test_chunker.py`; compare with `uv run python -m eval.run_eval --chunk-size N --overlap M --hybrid on --llm fake` |
| **Top-k** | `RETRIEVAL_TOP_K` in `.env` (used by `services/answer_service.py` and `routers/retrieve.py`). Candidate pool: `RETRIEVAL_CANDIDATES`. Debug endpoint accepts `top_k` 1–20 (`schemas.py`). | `uv run pytest tests/integration/test_retrieval.py::test_retrieve_respects_top_k` |
| **No-answer threshold** | `MIN_SIMILARITY` in `.env`. Logic: `backend/app/retrieval/gate.py`. Re-run the eval with real embeddings before moving it. | `uv run pytest tests/unit/test_gate.py tests/integration/test_no_answer_gate.py` |
| **Turn hybrid search off/on** | `HYBRID_ENABLED` in `.env`. Fusion: `retrieval/rrf.py`, `retrieval/hybrid.py`. | `uv run pytest tests/unit/test_rrf.py tests/integration/test_retrieval.py` |
| **System prompt** | `SYSTEM_PROMPT_V1` in `backend/app/llm/prompts.py` (live text; version is `PROMPT_VERSION`, currently **v1.1**). **Bump** `PROMPT_VERSION` in `.env` (and `config.py` default) and record the new text in `docs/prompts.md`, or the answer cache can serve old answers. | `uv run pytest tests/unit/test_prompt_builder.py tests/security/test_injection.py` |
| **Follow-up retrieval** | Heuristic in `backend/app/services/follow_up_query.py` (wired from `rag_document_flow.py`). Adjust `looks_like_follow_up` / hints if short follow-ups still miss the prior topic. | `uv run pytest tests/unit/test_follow_up_query.py` |
| **Delete a chat (API/UI)** | API: `DELETE /api/conversations/{id}` in `routers/chat.py`. UI: `ConversationSidebar` + `deleteConversation` in `lib/api.ts`. | `uv run pytest tests/integration/test_conversation_delete.py` |
| **Models** | `LLM_MODEL`, `LLM_FALLBACK_MODEL`, `LLM_PRICE_*` in `.env`. No code change. | `uv run pytest tests/unit/test_fallback.py` |

## Files and roles

| Change | Edit | Run |
|---|---|---|
| **Add an allowed file type** | `ALLOWED_EXTENSIONS` and magic-byte check in `backend/app/ingestion/file_validation.py`; parser + dispatch in `ingestion/parsers.py::parse_by_filename`; `ALLOWED_EXTENSIONS` in `frontend/src/lib/uploadRules.ts` (and the dropzone label). | `uv run pytest tests/unit/test_parsers.py tests/integration/test_upload_validation.py` |
| **Add a field to tickets** | 1) column on `Ticket` in `backend/app/models.py`; 2) new Alembic migration in `backend/migrations/versions/` (`uv run alembic revision -m "..."`, edit, `alembic upgrade head`); 3) `TicketCreateRequest` / `TicketPublic` in `schemas.py`; 4) `services/ticket_service.py` and `routers/tickets.py`; 5) `frontend/src/lib/types.ts`, the ticket card (`TicketOfferCard.tsx`) and `(app)/tickets/page.tsx`. | `uv run pytest tests/integration/test_ticket_flow.py`; `cd ../frontend && npx tsc --noEmit` |
| **Add a role or access level** | Role: `UserRole` in `models.py` plus a migration that extends the Postgres enum (`ALTER TYPE user_role ADD VALUE ...`). Visibility rule: `allowed_access_levels` in `security.py` (the single source of truth for every query). New document level: `AccessLevel` in `models.py` + migration, and decide who may set it in `routers/documents.py`. Seed users: `seed.py`. UI badge: `frontend/src/components/RoleBadge.tsx`. | `uv run pytest tests/security tests/unit/test_auth_roles.py` |

## Observability

| Change | Edit | Run |
|---|---|---|
| **Add or change a log field on `llm_calls`** | Column on `LlmCall` in `models.py`; migration; `LlmCallRecord` + `record_llm_call` in `services/audit_service.py`; where the value is produced (`services/answer_persistence.py`, `generation_audit.py`); expose it in `schemas.py::LlmCallDetail`, `services/admin_query_service.py` and `frontend/src/lib/types.ts`. | `uv run pytest tests/integration/test_audit.py tests/integration/test_admin.py` |
| **Change structured log lines** | `backend/app/logging_setup.py` (structlog processors). | `uv run pytest tests/unit` |
| **New audit event type** | Call `record_audit_event(...)` from `services/audit_service.py` where the action happens; event types are free-form strings today. | `tests/integration/test_audit.py` |

## Other common changes

| Change | Edit |
|---|---|
| Rate limits | `RATE_LIMIT_CHAT_PER_MINUTE`, `RATE_LIMIT_UPLOAD_PER_MINUTE` in `.env`; logic in `security_hardening.py` |
| Daily budgets | `DAILY_TOKEN_CAP_PER_USER`, `DAILY_COST_CAP_USD`; logic in `services/budget_service.py` |
| Cache lifetime / on-off | `CACHE_TTL_HOURS`, `CACHE_ENABLED`; logic in `services/cache_service.py` |
| Demo users | `seed.py` (idempotent) |
| Security headers / CSP | `Caddyfile` |
| Proxy/rewrite rules | `frontend/next.config.ts` (local) and `Caddyfile` (production) |
