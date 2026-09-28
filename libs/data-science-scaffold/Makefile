.SILENT:
.PHONY: format lint type-check test coverage complexity dependencies security quality maintainability

# Code tools are scoped to src and tests because template/ contains
# cookiecutter Jinja files that are not valid Python.
format:
	uv run ruff format src tests

lint:
	uv run ruff format --check src tests
	uv run ruff check src tests

type-check:
	uv run pyright src

test:
	uv run pytest

coverage:
	uv run pytest --cov --cov-report=term-missing:skip-covered --cov-fail-under=75

complexity:
	tmp=$$(mktemp); \
	uv run radon cc src -s -n C > $$tmp 2>&1 || { cat $$tmp; rm -f $$tmp; exit 1; }; \
	if [ -s $$tmp ]; then cat $$tmp; rm -f $$tmp; exit 1; fi; \
	rm -f $$tmp

dependencies:
	uv run deptry .

security:
	uv run bandit -q -r src -ll
	uv run vulture --min-confidence 80 src
	uv run semgrep --quiet --config auto .

maintainability:
	uv run xenon --max-absolute B --max-modules A --max-average A src

quality: lint type-check test coverage complexity dependencies security maintainability
