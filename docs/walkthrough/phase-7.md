# Phase 7 — Security stretch

**What I built:** `app/security_hardening.py` — a small, new file holding
exactly the two pieces AGENTS.md §3.2/§5.8 still needed: `RateLimiter`, an
in-memory sliding-window counter per `(user_id, action)` (the "simple
in-memory token bucket" §3.2 explicitly allows), wired as FastAPI
dependencies `require_chat_rate_limit` / `require_upload_rate_limit` onto
`POST /api/chat/stream` and `POST /api/documents` → `429` once a user's
per-minute cap (`RATE_LIMIT_CHAT_PER_MINUTE`, new
`RATE_LIMIT_UPLOAD_PER_MINUTE`) is exceeded; and
`matches_injection_pattern`, a cheap regex flagger wired into
`answer_service.py` (on every question) and `ingestion/pipeline.py` (on
every parsed document) that only ever **logs**
`audit_events.event_type = "injection_pattern_flagged"` — it never
blocks, rewrites, or refuses anything. `require_csrf_header` (already in
`security.py`) is now also applied to `POST`/`DELETE /api/documents`,
which had been missed — chat and tickets already had it.

**The access-control gap I actually found and fixed:** the upload
endpoint let an **employee** re-upload over an existing **manager-only**
document's filename and silently downgrade it to `access_level=all` (the
form default), because the "only managers may *create* a manager-only
doc" check never looked at what the *existing* row already was. That's a
real privilege-escalation path — guess or learn a manager-only filename,
upload a dummy file over it, and the ACL that used to protect it is just
gone. Fixed in `routers/documents.py` by also rejecting the re-upload
(403) when the existing document is already `managers`-level and the
caller is an employee, keeping the one rule "only this function writes
`documents.access_level`" true in both directions, not just one.

**Tests added, all against the real `pgvector/pgvector:pg16` container,
no API keys:**
- `tests/security/test_canary_leakage.py` (7 tests) — a manager-only doc
  containing `CANARY-7f3a-SALARY-BANDS` never comes back for an employee
  across 20+ adversarial phrasings (direct asks, "ignore the rules",
  role-play jailbreaks, five other languages) run through `retrieve()`
  directly; the canary is absent from the actual `ChatMessage` list
  `FakeLlm` recorded and from every SSE event on a real `/api/chat/stream`
  call that *did* reach the LLM; `GET` on its document/chunk 404s, not
  403s, for an employee.
- `tests/security/test_injection.py` (8 tests) — ingesting the real
  `sample-data/docs/zz-injection-test.md` logs the flag but still reaches
  `ready`; a question containing an injection phrase is flagged but never
  rejected; `SYSTEM_PROMPT_V1` states the untrusted-data rule;
  `build_user_message` escapes a forged `</source>` so injected content
  can never break out of its `<source>` element; and — the one that
  actually exercises the real defence, not just the prompt text — a
  `FakeLlm` scripted to "obey" the injected instructions and answer
  `"APPROVED"` with no citation comes back `status=ungrounded` with a
  ticket offer, because `check_grounding` (§5.11), not the model's good
  behaviour, is what catches it.
- `tests/security/test_authz.py` (9 tests) — a real, non-overridden
  `require_user` 401s with no cookie (even with the CSRF header present,
  so the two checks are never confused); the Phase-5 admin router's
  `require_role(UserRole.ADMIN)` 403s for both an employee and a manager
  and 200s for an admin; chat/upload/delete all 403 without the CSRF
  header; and the new rate limiters 429 on the 3rd chat request and the
  2nd upload once their per-minute caps are overridden down to 2 / 1 for
  the test via `app.dependency_overrides[get_settings]`.

**One real bug in my own test, caught by running it, not by reading
it:** my first cut of the "chat rate limit" and "canary never leaks via
chat" tests opened the SSE stream with `client.stream(...)` and asserted
only on `response.status_code`, never reading the body. `stream_chat_answer`
is a generator wrapped by `EventSourceResponse` — it only actually runs
as its output is consumed, so none of the code after the first `yield`
(including my own injection-flag audit write) had executed yet when the
test asserted. The assertion on `AuditEvent` existing failed with no
stack trace to point at the real cause. Fixed by always draining the
stream with the existing `read_sse_events()` helper before asserting on
anything the generator's body is responsible for — the same pattern every
other chat test in this repo already used; I just didn't copy it.

**Why rate limiting is in-memory, not a new table:** AGENTS.md §3.2
explicitly lists "simple in-DB or in-memory token bucket" as acceptable,
and a new table would need a migration plus the exact same race-condition
care the rest of this project already gives the database (`FOR UPDATE
SKIP LOCKED`, atomic swaps) for something that resets fine on a restart
in a single-process demo deployment. The trade-off is written directly
in `security_hardening.py`'s docstring: it is process-local, so a
multi-instance deployment would need to move it into Postgres — not
hidden, just not built, because nothing in this phase's spec needed it.

**What I verified for real:** 24 new security tests, plus the existing
115-test suite (Phases 0–6, including the Phase 5 admin suite built
concurrently with this one) — **139 tests, all passing** — against the
real database at `localhost:55432`. `ruff check app tests` and `mypy app`
(68 files) are both clean. Every existing test that posts or deletes
against `/api/documents` (`test_document_endpoints.py`,
`test_upload_validation.py`, `test_reupload.py`) was updated to send the
CSRF header now that the route actually enforces it.

**Honest note on this environment:** this repo was being built by a
second, concurrent agent (Phase 5's admin dashboard — `admin.py`,
`admin_stats_service.py`, `admin_query_service.py`,
`tests/integration/test_admin.py`, and extending `seed.py`) running its
own `pytest` against the exact same shared Postgres container at the
same time I was testing this phase. Both test suites' `db` fixtures
`TRUNCATE` the same tables before every test, so a full-suite run started
while the other agent's suite was mid-run intermittently raised
`ObjectDeletedError` / `InvalidRequestError` / `ForeignKeyViolation` on
rows that vanished out from under a just-committed object — never the
same failure twice, never reproducible in isolation. Every test this
phase added or touched was re-run standalone (and the full suite was
re-run clean at least twice, 139/139) specifically to separate that
shared-sandbox artifact from a real defect; none were found. A real
multi-agent deployment would give each agent its own ephemeral test
database precisely to avoid this.

**Left unfinished (expected — later phases):** the frontend's upload
page does not yet show a friendly "please wait" state for a 429 — that's
Phase 6/9 UI polish. `docs/eval.md`'s 2 injection questions against a
*real* model (not `FakeLlm`) are Phase 8 work; this phase proves the
deterministic defences hold against a scripted worst case, which is what
can be proven without an API key.
