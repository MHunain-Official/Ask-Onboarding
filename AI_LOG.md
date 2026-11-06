# AI Log

This log describes how AI tools were used to build this repo. It is written from the phase notes in `docs/walkthrough/` and the repo history available to the agent that wrote it, not from memory. Where something was not done or not verified, it says so. The owner should read it and correct anything that doesn't match what they remember.

## Tools

- **Cursor agents** (LLM-based coding agents) built the repo phase by phase, following `AGENTS.md` (the build playbook, copied from `Build_PlayBook.md`) and the rules in `.cursor/rules/`.
- Some phases ran in **concurrent agent sessions** against the same working tree and the same local Postgres container (see Phase 5 and 7 notes). That caused intermittent test flakiness, described below.
- The exact model names used per phase were not recorded in the repo; the owner should fill them in if reviewers ask.
- No eval or test in the repo calls a real model: tests use `FakeLlm` and `FakeEmbedder`.

## Key prompts (summarised)

The original prompts were not saved verbatim in the repo; these are summaries of the instruction each phase was given, which was always "read `AGENTS.md`, build this phase, run checks, write a walkthrough note, do not commit".

1. **Phase 0–1, foundation and auth.** Scaffold FastAPI, Next.js, compose with pgvector, CI, pre-commit; SQLAlchemy models and first migration; signed-cookie login with seeded demo users; JSON logs with request id.
2. **Phase 2, ingestion.** Parsers (md/txt/pdf), heading-aware token chunker with exact `char_start`/`char_end`, embedder interface plus OpenAI and fake implementations, worker with `FOR UPDATE SKIP LOCKED`, transactional chunk swap, upload/list/delete endpoints, re-upload tests.
3. **Phase 3, retrieval.** Access-filtered vector search, full-text search, RRF hybrid, similarity gate, `/api/retrieve`; prove hybrid helps with a deliberate test.
4. **Phase 4, answering.** LLM client interface, OpenRouter streaming, prompt v1 and builder, SSE chat, no-answer gate and ticket tool, ACL-scoped answer cache, fallback model, circuit breaker, budgets, single-flight, grounding checks, tickets.
5. **Phase 5, audit and admin.** `llm_calls` and `audit_events` recording, admin stats and request-detail endpoints, seed that queues the sample documents.
6. **Phase 6, frontend.** API client, tested SSE parser, login, upload, chat with citations and source drawer, tickets, admin, empty/loading/error states.
7. **Phase 7, security.** Rate limiting, CSRF on every state-changing route, injection-pattern flagger (log-only), canary leakage suite with 20+ adversarial questions, injection suite.
8. **Phase 8, evaluation.** 20-question set and harness comparing chunk sizes and hybrid on/off; write real numbers only.
9. **Phase 9, ship.** README, ARCHITECTURE, SECURITY, threat model, runbook, ADRs, cheatsheet, production compose and Caddyfile.

## Places the AI was wrong, and how each was caught

| # | Mistake | How it was caught | Fix |
|---|---|---|---|
| 1 | **Enum `.name` vs `.value`.** Postgres enum columns were written with the Python member name (`EMPLOYEE`) instead of the stored value (`employee`), so DB values and queries disagreed. | Tests against real Postgres. | Shared `pg_enum(...)` helper that stores `.value`. |
| 2 | **`EmailStr` rejecting `.local`.** The demo users `*@demo.local` failed Pydantic email validation because `.local` is a reserved special-use domain. | Login tests with the seeded users. | `LoginRequest.email` is a plain string with a light regex shape check; the route lower-cases it. |
| 3 | **`GENERATED` `tsv` column and `insert_default=None`.** SQLAlchemy sent an explicit `NULL` for `tsv`, which Postgres rejects on `GENERATED ALWAYS` columns, so every chunk insert failed. | `test_reupload.py` on real Postgres (a mock would have hidden it). | Declared with `Computed(...)` so the ORM omits it from INSERT/UPDATE. |
| 4 | **Grounding regex trailing `\b`.** A trailing `\b` can't match between two word characters, so "11pm" was never extracted as a number and a wrong time passed as "ok". It failed open. | `test_number_not_present_in_cited_source_is_ungrounded_fact`. | Leading negative lookbehind instead of the trailing boundary. |
| 5 | **Cache silently disabled by history order.** The user's question was saved before history was loaded, so every question looked like a follow-up and was never cacheable. Unit tests of the cache passed in isolation. | End-to-end test asserting a repeated question makes zero new LLM calls. | Load history before persisting the current turn, with a comment explaining why. |
| 6 | **Employee re-upload stripping manager ACL.** The "only managers may create manager-only docs" check ignored the existing row, so an employee could upload over a manager-only filename and downgrade it to `all`. A real privilege-escalation path. | Found during the Phase 7 access-control review. | `routers/documents.py` rejects (403) re-uploads by employees over `managers`-level documents. |
| 7 | **SSE generator side effects not drained.** Tests opened the stream and checked only the status code; `EventSourceResponse` runs the generator body as it is consumed, so audit writes hadn't happened and assertions failed with no clear cause. | Debugging a failing audit-event assertion. | Tests always drain the stream with `read_sse_events()` before asserting. |

Smaller ones recorded in the walkthrough notes: `UsageDaily` counters incremented before SQLAlchemy applied `default=0` (found by a manual smoke test); `seed_sample_documents` created its own session and was untestable (found when the test could not resolve host `db`); the frontend scaffold's `shadcn init` generated `import { cn } from "cn"`, an unrelated npm package (fixed to `@/lib/utils`).

**Environment caveat:** with two agents sharing one Postgres, each suite's `TRUNCATE` fixture occasionally deleted rows under the other's tests (`ForeignKeyViolation`, `ObjectDeletedError`). Affected tests were re-run in isolation and passed. This is a shared-sandbox artifact, not a code defect, but it means "all tests passed" claims in the phase notes come from re-runs, not from one concurrent run.

## What was not verified

- No live-model run exists: no OpenRouter or OpenAI call was made by any test or eval.
- Eval numbers are from `FakeEmbedder`; no LLM-judge, cost or live-latency data.
- Phase 9 files (compose prod, Caddyfile, docs) were written but not deployed; `docker-compose.prod.yml` has not been run, and the agent's environment had no `docker compose` plugin to even validate it.
- No browser-based visual check, Playwright test, Sonar, Trivy, gitleaks or pip-audit run.
- The repo has no commits yet, so the eval report shows commit `unavailable`.

## What the owner must hand-write or hand-review

The playbook requires the owner to be able to modify every line without AI. These four are the core to read line by line and, ideally, rewrite once by hand. Nothing in this log claims the owner has done so yet; update this section when it is true.

1. **Chunker core** — `backend/app/ingestion/chunker.py` (+ `markdown_sections.py`). Check the `parsed_text[char_start:char_end] == chunk text` invariant and the overlap logic. Test: `tests/unit/test_chunker.py`.
2. **Access filter** — `security.py::allowed_access_levels` and its use in `retrieval/vector_search.py`, `keyword_search.py`, `routers/documents.py`. Test: `tests/security/test_canary_leakage.py`.
3. **No-answer gate** — `retrieval/gate.py` and its use in `services/answer_service.py`. Tests: `tests/unit/test_gate.py`, `tests/integration/test_no_answer_gate.py`.
4. **Re-upload swap** — `routers/documents.py` (identity rules) and `ingestion/pipeline.py::_swap_chunks`. Test: `tests/integration/test_reupload.py`.

Also worth a careful read because past bugs lived there: `llm/grounding_check.py`, `services/cache_service.py`, `services/answer_service.py`.
