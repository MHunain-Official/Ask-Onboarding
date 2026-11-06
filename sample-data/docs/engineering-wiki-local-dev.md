# Engineering Wiki: Local Development

## Clone and run

```bash
git clone git@git.acme-onboarding.example:platform/api.git
cd api
cp .env.example .env
docker compose up --build
```

The API is available at http://localhost:8080 and the docs at http://localhost:8080/docs.

## Tests

Run `make test` before every push. The full suite takes about 4 minutes. Run a single test file with `pytest tests/unit/test_orders.py`.

## Branch naming

`feature/<ticket>-short-name`, `fix/<ticket>-short-name`. Example: `feature/PLAT-482-order-export`.

## Commit style

Use Conventional Commits: `feat:`, `fix:`, `docs:`, `chore:`. Subject line 72 characters or fewer.

## Local database

Postgres runs on port **5433** locally to avoid clashing with other installs. Reset it with `make db-reset`.

## Common problems

- Port 8080 already in use: run `lsof -i :8080` and stop the process.
- Docker out of disk space: `docker system prune -f`.
