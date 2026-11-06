# ADR 008: ACL-scoped exact answer cache

**Status:** accepted (exact cache on; semantic cache implemented as config only and off)

**Context.** Many onboarding questions repeat. Each skipped LLM call saves money and latency, but a cache is also a leak risk: a manager-scope answer served to an employee, or an answer from a document version that no longer exists.

**Decision.** `answer_cache` rows are keyed by `(scope, SHA-256 of normalised question, prompt_version, model)`, where `scope` is the user's allowed access levels (`all` or `all+managers`).
- On every hit, each `(document_id, version)` in `source_docs` must still be current, `ready`, and allowed for this user; otherwise the entry gets `invalidated_at` and the request is a miss. Re-upload and delete therefore make stale answers impossible, not just unlikely.
- Never cached: errors, partial streams, `ungrounded` answers, LLM "no answer" responses, answers to follow-up questions.
- Entries expire after `CACHE_TTL_HOURS`. The UI marks cached answers and offers Regenerate (bypass).
- Semantic cache (`SEMANTIC_CACHE_ENABLED=false`) stays off until an eval shows zero false hits on paraphrases; that eval has not been run.

**Proof.** `tests/integration/test_cache_scope.py`: a repeated question is served without a second LLM call; a manager never receives an employee-scoped entry; a re-upload invalidates the cached answer.

**Consequences.**
- A real bug here was found by test, not review: history was loaded after saving the current turn, so every question looked like a follow-up and the cache never fired (AI_LOG.md).
- Cache hits are still recorded in `llm_calls` with `cache_hit=exact`, and the admin tiles count them as "LLM calls avoided".
- No admin purge button; see the runbook for the SQL.
- Scope is only two levels; per-document ACLs would need a finer scope key.
