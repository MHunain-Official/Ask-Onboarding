# Threat model

Scope: the Ask Onboarding web app, its worker, its database, and its two external AI providers. Method: list assets, trust boundaries, then threats with the mitigation in code and the test that proves it. "Not tested" is stated where true.

## Assets

| Asset | Why it matters |
|---|---|
| Manager-only documents (e.g. salary bands) | Confidentiality; the canary string `CANARY-7f3a-SALARY-BANDS` stands in for them in tests |
| All document content and chunk embeddings | Company knowledge |
| `llm_calls` (full prompts and responses) and `audit_events` | Contain document text and user questions; the audit trail must be trustworthy |
| Session signing key (`SECRET_KEY`) | Forging it = impersonating any user |
| `LLM_API_KEY`, `EMBEDDING_API_KEY` | Cost and abuse |
| Availability and LLM budget | Cost abuse is a denial-of-wallet |
| Tickets | Integrity: must reflect a real human decision by the real user |

## Trust boundaries

1. **Browser ↔ Caddy/Next.js/FastAPI.** The browser is untrusted. Identity comes only from the signed cookie.
2. **FastAPI ↔ Postgres.** Trusted, same compose network; DB port not published in production.
3. **Backend/worker ↔ OpenAI and OpenRouter.** Outbound only. Document text and questions cross this boundary. Provider output is untrusted.
4. **Uploaded files ↔ parsers.** File bytes and extracted text are untrusted data.
5. **Retrieved chunk text ↔ the LLM prompt.** Untrusted data inside a trusted prompt.

## Threats, mitigations and proof

| # | Threat | Mitigation | Test / evidence |
|---|---|---|---|
| T1 | **Employee reads manager-only content** by direct request, paraphrase, other language, or jailbreak | `allowed_access_levels(user)` applied in the SQL `WHERE` of both vector and keyword search; `access_level` denormalised onto chunks; document list excludes manager docs | `test_canary_leakage.py`: 20+ adversarial phrasings via `retrieve()`; canary absent from the prompt recorded by `FakeLlm` and every SSE event; doc/chunk `GET` → 404; absent from employee list |
| T2 | **Existence leak** via 403 vs 404 | Forbidden docs/chunks return 404 | `test_get_canary_document_returns_404_not_403_for_employee`, `..._chunk_...` |
| T3 | **ACL downgrade by re-upload** (employee overwrites a manager-only filename) | Re-upload of a `managers` document by an employee is rejected with 403 | `test_upload_validation.py::test_employee_cannot_mark_document_managers_only` covers the create path; the re-upload rejection was added in Phase 7 and is described in `docs/walkthrough/phase-7.md`. **No dedicated regression test is named for the re-upload path; add one.** |
| T4 | **Cross-scope cache leak** or stale answer after re-upload/delete | Cache key includes scope, `prompt_version`, model; each hit re-validates `(document_id, version)`; re-upload invalidates | `test_cache_scope.py` (manager scope never gets an employee-scoped hit; re-upload invalidates) |
| T5 | **Prompt injection in a document** ("ignore rules", "answer APPROVED", "call the ticket tool") | Delimited sources, `</source>` escaping, untrusted-data rule in the prompt, tool cannot write, citation + grounding validation, log-only flagger | `test_injection.py` (prompt structure, escape, scripted obedient `FakeLlm` is caught as `ungrounded`, flagging does not block). Live-model resistance is **not** tested; only the fake model is |
| T6 | **Injection / jailbreak in the question** | Question always passed as `QUESTION:` data; same prompt rules; flagged in audit | `test_asking_a_question_with_an_injection_phrase_is_flagged_but_never_blocked` |
| T7 | **Model fabricates facts or citations** | Server-side citation validation; `ungrounded` status; numbers/dates/URLs/emails/commands must appear in cited chunks; never cached | `tests/unit/test_citation_validation.py`, grounding tests; Phase 4 regex bug fixed (see AI_LOG) |
| T8 | **Model takes action** (writes a ticket as someone else) | Single tool that only produces an offer; `POST /api/tickets` uses the session user and requires the CSRF header | `test_ticket_flow.py` |
| T9 | **System prompt leak** | Prompt rule 5; no API returns the prompt except the admin-only `llm-calls/{id}` | Admin authz tests; a leak-attempt question suite is **not** implemented |
| T10 | **Malicious upload** (spoofed type, traversal, huge file, empty, scanned/corrupt PDF) | Extension + magic bytes, size cap, UUID storage, sanitised display name, `MAX_PDF_PAGES`, failed status with reason | `test_upload_validation.py`, `test_parsers.py`. PDF-bomb and processing-timeout limits: page limit exists; a per-document wall-clock timeout is **not** implemented |
| T11 | **CSRF** on upload, delete, chat, tickets | `X-Requested-With` required + `SameSite=Lax` | `test_authz.py` |
| T12 | **Unauthenticated / wrong-role access** | `require_user` (401), router-level `require_role(ADMIN)` for `/api/admin` | `test_authz.py`, `test_audit.py` |
| T13 | **Session forgery or theft** | Signed cookie (`itsdangerous`), HttpOnly, `SameSite=Lax`, expiring, `Secure` when `APP_ENV=production` | Cookie flags not asserted by a test. Demo login has no password by design (see T20) |
| T14 | **Cost abuse / denial of wallet** | Per-user rate limits (chat, upload), question length cap, per-user daily token cap, global daily USD cap → retrieval-only mode, exact cache, no-answer gate | `test_authz.py` (429s); budget logic in `budget_service.py` (no dedicated integration test named here) |
| T15 | **Provider outage / retry storm** | Bounded retries, fallback model, circuit breaker, friendly error + degraded passages | `test_fallback.py`, `test_circuit_breaker.py`, `test_provider_failure.py` |
| T16 | **XSS via model output or document text** | `react-markdown` without raw HTML; source text as plain text with a single `<mark>`; CSP header at Caddy | Frontend tests cover SSE parser and citation chip only. **No XSS test.** CSP allows `'unsafe-inline'` scripts |
| T17 | **Secrets in repo, logs or browser** | Env-only config; `.env` git-ignored; `.env.example` placeholders; no `NEXT_PUBLIC_` secrets | gitleaks runs in pre-commit (`.pre-commit-config.yaml`), but **not in CI** and has not been run on history (there is none yet); no log-redaction filter or test |
| T18 | **Tampering with the audit trail** | App only inserts/selects `audit_events` in code; admin API is read-only | Append-only is by convention; **no DB-level grant** restricts UPDATE/DELETE |
| T19 | **Data exfiltration to third parties** | Documented trade-off: passages go to OpenRouter and OpenAI | See [SECURITY.md](../SECURITY.md); mitigation is operational (provider settings), not technical |
| T20 | **Anyone can log in as admin** (passwordless demo auth, seeded users) | Documented as demo-only; Caddy `basic_auth` block provided to gate a public demo; `SEED_ON_START=false` after seeding if desired | No technical fix without real auth. This is the largest known risk of a public deployment |
| T21 | **Container compromise** | Non-root backend image, `no-new-privileges` and `cap_drop: ALL` in prod compose (not on Postgres/Caddy), DB unpublished | Not scanned with Trivy; read-only filesystems not applied |
| T22 | **Silent fake clients in production** (empty keys) | Logged warning | **Unmitigated.** Check `docker compose logs backend` for `llm.using_fake_client` after deploy |

## Residual risks, in priority order

1. Demo auth on a public URL (T20).
2. Third-party processing of document text (T19).
3. Unproven live-model behaviour for injection resistance and `MIN_SIMILARITY` (T5, T9).
4. Missing scans and CI gates (T17, T21) and missing regression/XSS tests (T3, T16).
