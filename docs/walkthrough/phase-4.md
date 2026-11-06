# Phase 4 — Answering

**What I built:** the full chat pipeline from `POST /api/chat/stream`
(SSE) down to a persisted, audited answer. An `LlmClient` protocol
(`app/llm/base.py`) behind which `OpenAiCompatibleClient` (real
OpenRouter calls, bounded retries) and `FakeLlm` (scripted, test-only)
both sit; `fallback.py` (primary model, then `LLM_FALLBACK_MODEL`, never
silently on a content refusal) and `circuit_breaker.py` (open after N
consecutive failures, half-open after a cooldown) around it;
`prompts.py` (prompt v1, source numbering, `</source>` escaping, 4-turn
history); `grounding_check.py` (deterministic citation + fact checks, no
extra LLM call). `answer_service.py` orchestrates: query router → exact
answer cache (ACL-scoped) → retrieve → no-answer gate → budget check →
single-flight → stream + validate + persist + cache-write. `tickets.py`
and `chat.py` routers, both CSRF-protected on state-changing routes.

**Why this shape:** every layer in AGENTS.md §5.10 that can avoid an LLM
call does, in order, before any model is touched — small talk, the exact
cache, and the similarity gate are all plain Python/SQL, not prompts.
The streaming code is built around Python's `yield from` + generator
return values on purpose: a sync generator can stream SSE tokens to the
browser live *and* hand back the aggregated text/tool-call/usage to the
caller once it's done, without buffering the whole answer first and
without any extra plumbing (no queues, no callbacks). The chain is
`answer_service` → `single_flight_dispatch` → `answer_generation` →
`answer_persistence`, each one split out specifically to keep every file
under 200 lines while the generator delegation stays intact.

**Single-flight, honestly scoped down:** true live fan-out of one
generation to N identical concurrent requests would need pub/sub, which
AGENTS.md rules out (no Redis). What's actually built: a leader computes
and streams normally; a follower waits on the leader and then replays the
*finished* answer in one block, not token-by-token. Documented as a
known limitation in `single_flight_dispatch.py`, not hidden.

**Two bugs AI introduced and I caught by testing, not by reading code:**

1. **Grounding fact regex.** `\b\d[\d,]*...\b` looked right but a
   trailing `\b` can never match between two word characters — so "11pm"
   never matched as a number at all, and a wrong time like "11pm" when the
   source said "5pm" silently passed grounding as "ok" with zero facts
   checked. A trivial-looking regex that *looks* conservative was
   actually failing open. Caught by `test_number_not_present_in_cited_source_is_ungrounded_fact`
   failing; fixed by replacing the trailing `\b` with a leading negative
   lookbehind (`(?<![\w.])`) that still rejects numbers glued inside a
   larger token like "V2" but allows a unit letter straight after the
   digits.

2. **History-ordering bug that silently disabled caching.**
   `answer_service.py` persisted the user's question *before* calling
   `load_history_messages()`. That message then showed up as the newest
   row in its own history, so every single question — including the very
   first one in a brand-new conversation — was treated as a "follow-up"
   and `cacheable` was always `False`. The exact-cache (§5.10 L1) was
   silently dead code: it would pass every unit test of `cache_service.py`
   in isolation (those call the cache functions directly) while never
   actually firing end-to-end. It also meant the model saw the bare
   question twice: once as a plain history turn, once wrapped in the
   SOURCES/QUESTION block. Caught by `test_second_identical_question_is_served_from_cache_without_calling_llm`
   asserting the second ask made zero new `FakeLlm` calls and getting one
   instead — not caught by reading the orchestration code, which reads
   perfectly plausibly top-to-bottom. Fixed by loading history before
   persisting the current turn's message, with a comment explaining why
   the order matters.

A third, smaller bug (`UsageDaily` row created without explicit `0`
defaults, then incremented with `+=` before SQLAlchemy's `default=0` had
a chance to apply at flush) was caught the same way: a manual smoke test
of the full RAG path, not a code review.

**What I verified for real:** the full suite — 61 Phase 0–3 tests plus
44 new ones (17 unit: prompt builder, grounding/citations, query router,
circuit breaker, fallback, single-flight; 27 integration: no-answer gate,
ticket flow + CSRF + dedupe + role visibility, cache scope isolation +
re-upload invalidation, SSE event ordering + full audit-row persistence,
provider-failure friendly error) — all **105 pass** against the real
`pgvector/pgvector:pg16` container at `localhost:55432`, no API keys
anywhere. `ruff check`, `ruff format --check`, and `mypy app` are all
clean. Every file under `app/llm/`, `app/services/`, and the two new
routers is under 200 lines (largest is 194).

**Left unfinished (expected — later phases):** semantic cache
(`SEMANTIC_CACHE_ENABLED=false`) and the extractive shortcut
(`EXTRACTIVE_SHORTCUT_ENABLED=false`) are config flags and stubs only, as
instructed — turning them on needs the eval harness from Phase 8 to prove
zero false hits first. The `/admin` audit UI, rate limiting, and the
injection-document test suite are Phase 5/7 work, not this phase's.
