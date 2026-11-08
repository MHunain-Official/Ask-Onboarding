# Ask Onboarding

A RAG web app that answers employee questions **only from uploaded documents**, shows **exact citations**, says **"I don't know"** when the documents don't contain the answer, and offers to open a **help-desk ticket** instead of guessing.

- **Local:** <http://localhost:3000> via `docker compose up --build` (verified running with real OpenAI embeddings + OpenRouter answers).
- **Deployed:** frontend <https://ask-onboarding.vercel.app> · API <http://13.140.183.22:18083> (`/health` ok). Demo video and screenshots are owner-recorded separately (see [docs/runbook.md](docs/runbook.md)).
- **Stack:** Next.js (App Router, TypeScript, Tailwind, shadcn/ui) · FastAPI (Python 3.12) · PostgreSQL 16 + pgvector · OpenAI embeddings · OpenRouter for answers.
- **Design docs:** [ARCHITECTURE.md](ARCHITECTURE.md) · [SECURITY.md](SECURITY.md) · [docs/agent-ops.md](docs/agent-ops.md) · [docs/eval.md](docs/eval.md) · [docs/cheatsheet.md](docs/cheatsheet.md) · [AI_LOG.md](AI_LOG.md)

## Quick start (local)

```bash
cp .env.example .env
# edit .env: set LLM_API_KEY (OpenRouter) and EMBEDDING_API_KEY (OpenAI);
# also set SECRET_KEY to a long random string
docker compose up --build
```

Open <http://localhost:3000>. On first start the backend runs migrations, seeds the demo users and queues the 25 sample documents; the worker ingests them (watch `/upload` go `queued → processing → ready`).

> **Empty keys do not fail.** If `LLM_API_KEY` or `EMBEDDING_API_KEY` is empty, the app logs a warning and uses the deterministic `FakeLlm` / `FakeEmbedder` so it still runs offline. Answers in that mode are scripted, not real. Set both keys for a real demo.

### Demo logins (passwordless, demo-only)

| Email | Role | Sees |
|---|---|---|
| `employee@demo.local` | employee | `all` documents |
| `manager@demo.local` | manager | `all` + manager-only documents |
| `admin@demo.local` | admin | everything, plus `/admin` audit pages |

Login takes an email only. That is a deliberate demo shortcut, not a production auth scheme (see limitations).

### Pages

`/login` · `/chat` (streaming answers, citation chips, source drawer, ticket offer) · `/upload` (PDF/MD/TXT, status table) · `/tickets` · `/admin` (stats, request table with full prompt/response, audit events).

## Screenshots

Not captured yet. Run the app locally and capture: login, upload status table, chat with the citation drawer open, no-answer + ticket offer, tickets, admin request detail. Save them under `docs/screenshots/` and link them here.

## Features vs. assignment

| Requirement | Status | Where |
|---|---|---|
| Upload PDF/MD/TXT; list with processing/ready/failed | Built | `routers/documents.py`, `frontend/src/app/(app)/upload` |
| Streaming chat with history | Built | `routers/chat.py`, `services/answer_service.py`, `lib/sse.ts` |
| Delete own conversation from history | Built | `DELETE /api/conversations/{id}`, `ConversationSidebar` |
| Follow-up retrieval stays on prior topic | Built (no LLM rewriter) | `services/follow_up_query.py` |
| Clickable citations open source + exact passage | Built | `GET /api/chunks/{id}`, `SourceDrawer` |
| Empty / loading / error states | Built | `frontend/src/app` |
| Ingestion → chunks → embeddings → pgvector | Built + live-verified (e.g. uploaded HR PDF → 40 chunks `ready`) | `app/ingestion/`, `app/embeddings/` |
| Retrieval endpoint + streaming answer endpoint | Built + live-verified with OpenRouter | `POST /api/retrieve`, `POST /api/chat/stream` |
| Honest "no answer" + ticket offer tool | Built (live `llm_calls` include `no_answer` rows) | `retrieval/gate.py`, `llm/tools.py`, `services/ticket_service.py` |
| Re-upload replaces old chunks atomically | Built, tested | `ingestion/pipeline.py::_swap_chunks`, `tests/integration/test_reupload.py` |
| Keys server-side, `.env.example` | Built | `app/config.py`, `.env.example` |
| `docker compose up` from a fresh clone | Built; local stack verified running | `docker-compose.yml` |
| Automated tests (chunking, retrieval, no-answer) | Built | `backend/tests/` |
| Stretch: evaluation harness | Built | `backend/eval/`, [docs/eval.md](docs/eval.md) |
| Stretch: access control, proven | Built | `security.py`, `tests/security/test_canary_leakage.py` |
| Stretch: prompt-injection defence + test | Built | `tests/security/test_injection.py` |
| Stretch: audit/observability admin | Built | `routers/admin.py`, `llm_calls`, `audit_events` |
| README, ARCHITECTURE, AI_LOG | Written | this repo root |
| Live deployment | Backend + frontend deployed | Vercel + VPS API (see top of README) |
| Demo video / screenshots | Owner records separately | not part of the code deliverable |

## Evaluation results

See [docs/eval.md](docs/eval.md) for the full write-up. Short version:

**A. Live product (real OpenAI embeddings + OpenRouter)** — verified in the local DB (commit `97ecb9c`): 27 ready docs / 154 chunks; uploaded `HR-Policy-Revised-JUNE-2022.pdf` produced **40 chunks**; chat rows use `openai/gpt-4o-mini` with real token/cost accounting; statuses seen include `ok`, `no_answer`, and `ungrounded`.

**B. Formal harness table (chunk size × hybrid)** — still scored with `FakeEmbedder` / `FakeLlm` so the comparison is cheap and reproducible (generated 2026-11-06). These numbers chose the defaults; they are not live-embedding hit-rates.

| Chunk | Overlap | Hybrid | Hit-rate@5 | MRR | Unanswerable refusal | Canary leaks | Injection leaks |
|---:|---:|---|---:|---:|---:|---:|---:|
| 300 | 60 | off | 95.0% (19/20) | 0.742 | 100.0% | 0 | 0 |
| 300 | 60 | on | 100.0% (20/20) | 0.892 | 100.0% | 0 | 0 |
| 500 | 80 | off | 100.0% (20/20) | 0.760 | 100.0% | 0 | 0 |
| 500 | 80 | on | 100.0% (20/20) | 0.892 | 100.0% | 0 | 0 |

What the harness numbers support: hybrid raised MRR from 0.760 to 0.892 at 500/80, and 500/80 matched or beat 300/60 on hit-rate → defaults are chunk 500 / overlap 80 / hybrid on.

Still not measured in the harness: retrieval hit-rate with `text-embedding-3-small`, two-model comparison, LLM-as-judge, cache hit rate on a repeat set, semantic-cache false-hit rate (semantic cache stays **off**), and a tuned `MIN_SIMILARITY` on real embeddings (0.30 remains the playbook starting value).
## Running checks

```bash
make check          # ruff + mypy + eslint + tsc + pytest + vitest
make test           # backend and frontend tests only
make lint           # lint only
make eval           # backend/eval/run_eval.py (see docs/eval.md for flags)
```

Backend integration and security tests need a real, migrated Postgres with pgvector, and skip when none is reachable. Start one with `docker compose up -d db` (published on host port `55432`), migrate it, then point the tests at it:

```bash
export DATABASE_URL=postgresql+psycopg://app:app@localhost:55432/askonboarding
export TEST_DATABASE_URL=$DATABASE_URL
make migrate
make test
```

The test fixtures `TRUNCATE` tables, so never point `TEST_DATABASE_URL` at a database with data you care about. No API keys are needed for any test.

Reproduce the eval table:

```bash
cd backend
uv run python -m eval.run_eval --compare --llm fake
```

`--llm real` calls OpenRouter and costs money; run it only with real keys, and paste the resulting numbers into `docs/eval.md` with the run date and commit.

## Production deploy

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Adds Caddy (automatic HTTPS), unpublishes the DB/backend/frontend ports, and sets restart policies, resource limits and log rotation. Full steps, backups and rollback: [docs/runbook.md](docs/runbook.md). This has not been run against a real VPS yet.

## Configuration

Every setting is an environment variable read in one place, `backend/app/config.py`; the documented list with comments is `.env.example`. Key ones:

| Variable | Default | Purpose |
|---|---|---|
| `LLM_MODEL`, `LLM_FALLBACK_MODEL` | `openai/gpt-4o-mini` | OpenRouter primary and fallback models |
| `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS` | `text-embedding-3-small`, `1536` | Must match the DB `vector(1536)` column |
| `CHUNK_TARGET_TOKENS`, `CHUNK_OVERLAP_TOKENS` | `500`, `80` | Chunking |
| `RETRIEVAL_TOP_K`, `HYBRID_ENABLED`, `MIN_SIMILARITY` | `5`, `true`, `0.30` | Retrieval and the no-answer gate |
| `CACHE_ENABLED`, `SEMANTIC_CACHE_ENABLED` | `true`, `false` | Exact answer cache on; semantic cache off |
| `RATE_LIMIT_CHAT_PER_MINUTE`, `RATE_LIMIT_UPLOAD_PER_MINUTE` | `10`, `20` | Per-user, in-memory |
| `DAILY_TOKEN_CAP_PER_USER`, `DAILY_COST_CAP_USD` | `100000`, `10` | Over cap → retrieval-only mode |

## Known limitations

Stated plainly so nobody has to find them in review:

- **Demo auth.** Passwordless login by email. Never expose the demo users on the open internet without the Caddy `basic_auth` block or real auth.
- **Silent fake fallback.** Empty API keys switch to `FakeLlm`/`FakeEmbedder` with only a log warning. No startup check refuses to run in production without keys.
- **Two kinds of “eval”.** The running app uses **real** OpenAI embeddings and OpenRouter (see live verification in [docs/eval.md](docs/eval.md)). The **harness comparison table** (hit-rate/MRR by chunk size / hybrid) still uses `FakeEmbedder` so it stays free and deterministic. A full 20-question harness pass with live embeddings + LLM-as-judge has not been pasted yet.
- **`MIN_SIMILARITY=0.30` is untuned on real embeddings** (it works in live chat, but was not grid-searched).
- **Embeddings:** preferred path is OpenAI direct. If OpenAI returns 429/no credits, point `EMBEDDING_BASE_URL` / `EMBEDDING_API_KEY` / `EMBEDDING_MODEL` at OpenRouter (documented in `.env.example`) — the `Embedder` interface already supports a custom base URL.
- **English-only full-text search** (`to_tsvector('english', ...)`).
- **Scanned/image-only PDFs are rejected** (no OCR). PDF page limit is `MAX_PDF_PAGES`.
- **Single worker, no retry queue UI.** Scaling is "start more worker containers"; untested.
- **Rate limiter and circuit breaker are in-memory**, per process; a multi-instance deployment would need them in Postgres.
- **Single-flight followers get the finished answer in one block**, not token by token.
- **No keyword-only fallback when the embedding API is down at query time** (playbook §5.12 #3), no startup check that `EMBEDDING_DIMENSIONS` matches the DB column (#6), and no log-redaction filter (#38). See [docs/runbook.md](docs/runbook.md) for the full list.
- **`audit_events` is append-only by convention, not by database grants.**
- **No audit retention command**; the runbook gives the SQL.
- **CSP allows `'unsafe-inline'` scripts** (Next.js bootstrap) until nonces are added.
- **No streaming resume** after a dropped connection; the partial answer is saved and Retry re-asks.
- **Frontend route protection is client-side**; the backend enforces auth on every API route.
- **No LLM query rewriter.** Short/referential follow-ups prepend the previous user question for **search only** (`follow_up_query.py`). A full rewrite model is not used.
- **Not built:** feedback thumbs, full LLM query rewriting, semantic cache enabled, extractive shortcut enabled, Playwright smoke test.
- **Not run by the agent:** Sonar, Trivy, gitleaks, pip-audit, a real-browser visual pass, a deployed SSE-through-Caddy check.

## Repository map

```
backend/app/        FastAPI app: routers/, services/, ingestion/, retrieval/, llm/, embeddings/
backend/eval/       questions.json, run_eval.py, report.md
backend/tests/      unit/, integration/, security/
frontend/src/       app/ (pages), components/, lib/ (api, sse), hooks/
sample-data/        25 fictional docs incl. manager-only canary and injection test doc
docs/               eval, prompts, runbook, threat model, ADRs, walkthrough notes, cheatsheet
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for commit style and checks, and [CHANGELOG.md](CHANGELOG.md).
