.SILENT:
.PHONY: format lint type-check test coverage complexity dependencies security maintainability

format:
	uv run ruff format .

lint:
	uv run ruff format --check .
	uv run ruff check .

type-check:
	uv run pyright src

test:
	uv run pytest -m "not integration"

coverage:
	uv run pytest -m "not integration" --cov --cov-report=term-missing:skip-covered --cov-fail-under=75

complexity:
	tmp=$$(mktemp); \
	uv run radon cc . -s -n C -e "*/node_modules/*" > $$tmp 2>&1 || { cat $$tmp; rm -f $$tmp; exit 1; }; \
	if [ -s $$tmp ]; then cat $$tmp; rm -f $$tmp; exit 1; fi; \
	rm -f $$tmp

dependencies:
	uv run deptry .

security:
	uv run bandit -q -r src docker -ll
	uv run vulture --min-confidence 80 src docker
	uv run semgrep --quiet --config auto .

maintainability:
	uv run xenon --max-absolute B --max-modules A --max-average A . -e "*/node_modules/*"

quality: lint type-check test coverage complexity dependencies security maintainability
