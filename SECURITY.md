# Security

This is a take-home/demo-grade application with real defences in the places that matter for a RAG system. It has **not** had an external security review. The full model is in [docs/threat-model.md](docs/threat-model.md); this page is the summary.

## Reporting a vulnerability

Do not open a public issue. Email the repository owner (add the contact address here before publishing; none is configured yet) with steps to reproduce, the affected route or file, and the impact. Expect an acknowledgement within a few days; this is a personal project with no SLA.

## What we defend, in one table

| Risk | Defence | Proof |
|---|---|---|
| Cross-role data leakage | `access_level` filter inside the retrieval SQL, never in the prompt or after generation; document/chunk endpoints return 404 (not 403) | `tests/security/test_canary_leakage.py` |
| Prompt injection in documents or questions | Sources wrapped in `<source>` tags with `</source>` escaped; system prompt says sources are untrusted; the one tool cannot write; citations and facts validated server-side; log-only regex flagger | `tests/security/test_injection.py` |
| Model acting on its own | One tool (`offer_help_desk_ticket`) that only produces an offer; the ticket is written by a separate authenticated endpoint with the user from the session | `tests/integration/test_ticket_flow.py` |
| Stale or cross-scope cached answers | Cache keyed by access scope, `prompt_version`, model; re-validated against current document versions on every hit | `tests/integration/test_cache_scope.py` |
| Malicious uploads | Extension **and** magic-byte check, size cap, UUID storage, sanitised display name | `tests/integration/test_upload_validation.py` |
| CSRF | Custom header required on state-changing routes plus `SameSite=Lax` cookie | `tests/security/test_authz.py` |
| Cost abuse | Per-user rate limits, input length cap, per-user token cap, global USD cap → retrieval-only mode | `tests/security/test_authz.py` (rate limits), `budget_service.py` |
| XSS from model output or documents | `react-markdown` without raw HTML; source text rendered as plain text | Frontend tests cover the SSE parser and citation chip only; no dedicated XSS test exists |
| Secrets in the browser | Keys only in backend env; frontend talks to same-origin `/api` | by construction (`next.config.ts`, `config.py`) |

## Data handling: where document text goes

**Document text leaves your network.** Every question sends the top retrieved passages and the question to **OpenRouter**, which forwards them to whichever upstream model provider serves the request; every ingested chunk is sent to **OpenAI** for embedding. Both providers have their own retention and training policies, and OpenRouter's depend on the selected model/provider and your account settings. Before loading real company documents:

- Read the current OpenRouter and OpenAI data-retention terms and configure account-level data controls (for example, opt out of training and logging where offered).
- Do not upload confidential material you are not allowed to send to third parties.
- The `llm_calls` table stores the full prompt and response (up to 100 KB per field) in **your** database, including passages from documents the asking user could read. Treat the admin role accordingly.

## Known gaps (also listed in the README)

- **Demo auth:** passwordless login by email. Do not expose it publicly without the Caddy `basic_auth` block or a real identity provider.
- **Fake fallback in production:** empty `LLM_API_KEY` / `EMBEDDING_API_KEY` silently switch to fake clients (logged as a warning only).
- **`audit_events` append-only is by convention**, not enforced by database grants (the playbook asks for INSERT+SELECT-only grants).
- **No log-redaction filter.** The code does not log keys or cookies by design, but nothing enforces it.
- **CSP uses `'unsafe-inline'` for scripts** (Next.js bootstrap). Frame embedding and other directives are locked down in the `Caddyfile`.
- **In-memory rate limiter and circuit breaker** are per process.
- **No embedding-dimension startup check** and **no keyword-only fallback** when embeddings are unavailable at query time.
- **Dependency and image scanning not run yet:** Dependabot config exists; `pip-audit`, `npm audit`, Trivy and gitleaks are not wired into CI.
- **No dedicated XSS test** for malicious markdown in uploaded documents (playbook §5.12 #36).
