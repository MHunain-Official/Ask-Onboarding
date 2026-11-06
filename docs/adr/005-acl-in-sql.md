# ADR 005: Access control enforced in the retrieval SQL

**Status:** accepted

**Context.** Some documents are manager-only. A language model cannot be trusted to withhold text it has been shown, and filtering results after retrieval risks forgetting a code path.

**Decision.**
- `documents.access_level` is copied to every `document_chunks` row.
- `security.py::allowed_access_levels(user)` is the only place that maps role to levels (employee → `all`; manager, admin → `all` + `managers`).
- Both retrieval queries put `WHERE access_level IN (...)` inside the SQL. A chunk the user may not read never leaves the database, never reaches the prompt, and never appears in an SSE event.
- Document list, content and chunk endpoints use the same helper; forbidden ones return **404**, not 403, so existence does not leak.
- The answer cache is keyed by scope (ADR 008).
- Uploads: only managers/admins may set `managers`; an employee may not overwrite an existing manager-only document (found and fixed in Phase 7).

**Proof.** `tests/security/test_canary_leakage.py`: the canary `CANARY-7f3a-SALARY-BANDS` never appears for an employee across 20+ adversarial phrasings, in the recorded LLM prompt, in SSE events, or via document/chunk `GET`.

**Consequences.**
- Two coarse levels only. Real deployments need per-document ACLs synced from the source system.
- Every new query that touches chunks must use the helper; the canary suite is the safety net, so extend it when adding query paths.
