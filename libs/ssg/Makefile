.SILENT:
.PHONY: format lint type-check test test-e2e coverage complexity dependencies security quality maintainability

format:
	uv run ruff format .

lint:
	uv run ruff format --check .
	uv run ruff check .

type-check:
	uv run pyright src

test:
	uv run pytest -m "not (playwright or docker)"

test-e2e:
	uv run pytest -m playwright

coverage:
	uv run pytest -m "not (playwright or docker)" --cov --cov-report=term-missing:skip-covered --cov-fail-under=75

complexity:
	tmp=$$(mktemp); \
	uv run radon cc . -s -n C -e "*/node_modules/*" > $$tmp 2>&1 || { cat $$tmp; rm -f $$tmp; exit 1; }; \
	if [ -s $$tmp ]; then cat $$tmp; rm -f $$tmp; exit 1; fi; \
	rm -f $$tmp

dependencies:
	uv run deptry .

security:
	uv run bandit -q -r src -ll
	uv run vulture --min-confidence 80 src
	uv run semgrep --quiet --config auto .

maintainability:
	uv run xenon --max-absolute B --max-modules A --max-average A . -e "*/node_modules/*"

quality: lint type-check test coverage complexity dependencies security maintainability
