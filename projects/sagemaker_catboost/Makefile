.SILENT:
.PHONY: format lint type-check quality sync

format:
	uv run ruff format src

lint:
	uv run ruff format --check src
	uv run ruff check src

type-check:
	uv run pyright src

sync:
	uv sync --all-packages

quality: format lint type-check
