.SILENT:
.PHONY: format lint type-check test coverage complexity dependencies security maintainability quality

format:
	uv run ruff format .

lint:
	uv run ruff format --check .
	uv run ruff check .

type-check:
	uv run pyright src

test:
	uv run pytest

coverage:
	uv run pytest --cov --cov-report=term-missing:skip-covered

complexity:
	tmp=$$(mktemp); \
	uv run radon cc . -s -n C -x "*/node_modules/*" > $$tmp 2>&1 || { cat $$tmp; rm -f $$tmp; exit 1; }; \
	if [ -s $$tmp ]; then cat $$tmp; rm -f $$tmp; exit 1; fi; \
	rm -f $$tmp

dependencies:
	uv run deptry .

security:
	uv run bandit -r src -ll
	uv run vulture src
	uv run semgrep --quiet --config auto .

maintainability:
	uv run xenon --max-absolute B --max-modules A --max-average A src

quality: lint type-check test coverage complexity dependencies security maintainability
