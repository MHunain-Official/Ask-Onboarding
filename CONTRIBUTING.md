# Contributing

Read `AGENTS.md` first: it is the build playbook and the source of the rules below. The overriding rule is that the owner must be able to understand and change every line without AI, so prefer boring, small, readable code.

## Setup

```bash
cp .env.example .env
docker compose up -d db                       # Postgres on host port 55432
cd backend && uv sync && cd ..
cd frontend && npm ci && cd ..
export DATABASE_URL=postgresql+psycopg://app:app@localhost:55432/askonboarding
export TEST_DATABASE_URL=$DATABASE_URL
make migrate
pre-commit install                            # ruff, gitleaks, whitespace and key checks
```

## Checks (run before every commit)

```bash
make check      # lint + typecheck + tests (ruff, mypy, eslint, tsc, pytest, vitest)
```

Individual targets: `make lint`, `make typecheck`, `make test`, `make eval`. No test needs an API key; AI calls are faked behind `LlmClient` and `Embedder`. Integration and security tests need the Postgres above and **truncate its tables**, so use a throwaway database.

## Code rules (short version)

- **Python:** ruff format + lint, type hints on every function, no `Any` without a comment, files under ~200 lines, functions under ~30. Config only through `backend/app/config.py`; never read `os.environ` elsewhere.
- **TypeScript:** `strict`, no `any`, components in `PascalCase.tsx`, all backend calls through `frontend/src/lib/api.ts`.
- **Comments** explain *why*, not what. No commented-out code, no TODOs on `main`.
- **Never hardcode** secrets, model names, prices or thresholds.
- **Security rules are not negotiable:** access control stays in the SQL `WHERE`; retrieved text is untrusted; the model's only tool never writes; never weaken a rule to make a test pass.
- **A bug fix starts with a failing test.**

## Commits

[Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `test:`, `docs:`, `chore:`, `refactor:`, `ci:`. Imperative subject, 72 characters or fewer, body explains *why* when not obvious. One logical change per commit, with its tests. No "WIP", "fix" or "update".

## Documentation

**Docs are part of the change.** If behaviour, APIs, prompts, config, security, deploy, or eval change, update the matching living docs in the **same** commit/PR. Cursor enforces this via `.cursor/rules/documentation.mdc`.

- Prompt changes: bump `PROMPT_VERSION` and add the new text to `docs/prompts.md`.
- Eval numbers: paste only real output of `make eval` with date and commit. Never estimate.
- New design decision: add a short ADR in `docs/adr/`.
- Each build phase ends with a note in `docs/walkthrough/phase-N.md`.
- Update [CHANGELOG.md](CHANGELOG.md) under *Unreleased*.
- Typical map: product path → `ARCHITECTURE.md`; features/limitations → `README.md`; owner “change X” → `docs/cheatsheet.md`; ops → `docs/runbook.md`.

See [docs/cheatsheet.md](docs/cheatsheet.md) for "to change X, edit Y, run Z".
