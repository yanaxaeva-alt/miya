.PHONY: setup dev test lint typecheck check clean

setup:
	@./scripts/dev.sh --setup-only

dev:
	@./scripts/dev.sh

test: setup
	@uv run pytest

lint: setup
	@uv run ruff check .
	@cd frontend && npm run lint

typecheck: setup
	@uv run mypy
	@cd frontend && npm run build

check: lint typecheck test

clean:
	@rm -rf .pytest_cache .mypy_cache .ruff_cache
	@rm -rf dist build src/*.egg-info
	@rm -rf frontend/dist frontend/.vite
