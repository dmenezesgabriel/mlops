.SILENT:
.PHONY: format lint type-check quality sync build-images test test-notebooks coverage complexity dependencies security maintainability

format:
	uv run ruff format src

build-images:
	docker build -f Dockerfile -t sagemaker-lightgbm:train ../../libs/sagemaker-local/docker
	docker build -f Dockerfile.inference -t sagemaker-lightgbm:inference ../../libs/sagemaker-local/docker

test:
	uv run pytest -m "not integration"

test-notebooks:
	/opt/mlops-venv/bin/python -m pytest -m integration

lint:
	uv run ruff format --check src
	uv run ruff check src

type-check:
	uv run pyright src

sync:
	uv sync --all-packages

coverage:
	uv run pytest -m "not integration" --cov --cov-report=term-missing:skip-covered --cov-fail-under=69

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

quality: format lint type-check test coverage complexity dependencies security maintainability
