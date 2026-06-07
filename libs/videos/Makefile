.SILENT:
.PHONY: format lint type-check test test-docker coverage complexity dependencies security quality

format:
	uv run ruff format .

lint:
	uv run ruff format --check .
	uv run ruff check .

type-check:
	uv run mypy src

test:
	uv run pytest -m "not docker"

test-docker:
	make -C ../.. test-videos-docker

coverage:
	uv run pytest -m "not docker" --cov --cov-report=term-missing:skip-covered

complexity:
	tmp=$$(mktemp); \
	uv run radon cc . -s -n C -x "*/node_modules/*" > $$tmp 2>&1 || { cat $$tmp; rm -f $$tmp; exit 1; }; \
	if [ -s $$tmp ]; then cat $$tmp; rm -f $$tmp; exit 1; fi; \
	rm -f $$tmp

dependencies:
	uv run deptry .

security:
	uv run semgrep --quiet --config auto .

quality: lint type-check test coverage complexity dependencies security
