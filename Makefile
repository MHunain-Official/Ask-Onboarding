.PHONY: up down build test lint typecheck check eval seed migrate logs

up:
	docker compose up --build

down:
	docker compose down

build:
	docker compose build

migrate:
	cd backend && uv run alembic upgrade head

seed:
	cd backend && uv run python -m app.seed

test:
	cd backend && uv run pytest -q --cov=app --cov-report=term-missing --cov-fail-under=60
	cd frontend && npm test -- --run

lint:
	cd backend && uv run ruff check app tests
	cd backend && uv run ruff format --check app tests
	cd frontend && npm run lint
	cd frontend && npx prettier --check "src/**/*.{ts,tsx,css}"

typecheck:
	cd backend && uv run mypy app
	cd frontend && npx tsc --noEmit

check: lint typecheck test

eval:
	cd backend && uv run python -m eval.run_eval

logs:
	docker compose logs -f --tail=200
