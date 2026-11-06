# Phase 9 — Ship documentation and production infrastructure

**What I built:** the documents a reviewer reads first (`README.md`, `ARCHITECTURE.md` with two Mermaid diagrams and the six required answers, `AI_LOG.md`, `SECURITY.md`, `docs/threat-model.md`), the operator documents (`docs/runbook.md`, `docs/cheatsheet.md`, ADRs 001–008, `CONTRIBUTING.md`, `CHANGELOG.md`), and production infra (`docker-compose.prod.yml`, `Caddyfile`, `.github/dependabot.yml`). `.env.example` gained `RATE_LIMIT_UPLOAD_PER_MINUTE` (it exists in `config.py` but was missing) and the production-only `DOMAIN`, `ACME_EMAIL`, `POSTGRES_PASSWORD`.

**Why it is shaped this way:** the prod compose file is an override of the dev one, so there is one source of truth for the services. It unpublishes the DB, backend and frontend ports with `!reset`, adds restart policies, memory limits, log rotation, healthchecks, `no-new-privileges` and `cap_drop: ALL` on the app containers, and starts the worker only after the backend is healthy (so migrations have run). Caddy sends `/api/*` and `/health` straight to FastAPI with `flush_interval -1`, because routing SSE through the Next.js rewrite risks buffering; everything else goes to Next.js.

**Numbers:** every eval number in the docs is copied from `docs/eval.md` (fake embedder, fake LLM, commit `unavailable`) and labelled as such. Nothing was estimated except the cost model in `ARCHITECTURE.md` §3, which is shown as arithmetic on placeholder prices.

**Verified:** the compose override YAML parses and merges (checked with a YAML loader that understands `!reset`). That is all. `docker compose` is not installed in this environment, so neither compose file was validated with Compose, and nothing was built or deployed. The Caddyfile was not validated (no `caddy` binary).

**Honest gaps found while writing the docs (all recorded in README, SECURITY, runbook §11):**
- Empty API keys silently switch to `FakeLlm`/`FakeEmbedder` in any environment, including production.
- Not built from the playbook: keyword-only fallback when embeddings fail at query time (#3), embedding-dimension startup check (#6), log-redaction filter (#38), audit retention command, DB-level append-only grants on `audit_events`, SSE heartbeat/proxy behaviour verified behind Caddy (#11), admin cache purge, per-document processing timeout.
- No dedicated regression test for "employee cannot overwrite a manager-only document" on re-upload, and no XSS test for uploaded markdown.
- CI still lacks Sonar, Trivy, gitleaks-in-CI, `pip-audit`, `npm audit`, and a docker-compose build + `/health` smoke test; the nightly eval schedule is not configured.
- Migration failure during `up -d --build` causes an outage rather than keeping old containers (runbook §2).
- No demo video, no screenshots, no live URL, no Playwright smoke test, no real-model eval, `MIN_SIMILARITY` untuned. `docs/prompts.md` rule-by-rule rationale was not revisited.
- The repo has no commits; the playbook's commit plan and gitleaks-on-history have not happened.

**Owner next steps:** read the four hand-review areas in `AI_LOG.md`; run `make check` against a throwaway Postgres; run a live eval with real keys and replace the placeholder section of `docs/eval.md`; tune `MIN_SIMILARITY`; test the prod compose on a VPS, including SSE through Caddy and a backup restore; add the missing CI jobs.
