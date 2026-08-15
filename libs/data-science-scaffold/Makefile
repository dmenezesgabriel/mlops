.SILENT:
.PHONY: format lint type-check test coverage complexity dependencies security quality

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
	uv run pytest --cov --cov-report=term-missing:skip-covered

complexity:
	tmp=$$(mktemp); \
	uv run radon cc src -s -n C > $$tmp 2>&1 || { cat $$tmp; rm -f $$tmp; exit 1; }; \
	if [ -s $$tmp ]; then cat $$tmp; rm -f $$tmp; exit 1; fi; \
	rm -f $$tmp

dependencies:
	uv run deptry .

security:
	uv run semgrep --quiet --config auto .

quality: lint type-check test coverage complexity dependencies security
