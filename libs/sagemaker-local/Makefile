.SILENT:
.PHONY: format lint type-check test

format:
	uv run ruff format .

lint:
	uv run ruff format --check .
	uv run ruff check .

type-check:
	uv run pyright src

test:
	uv run pytest -m "not integration"

quality: lint type-check test
