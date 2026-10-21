.SILENT:
.PHONY: format lint up-% ps down type-check quality sync build-images test test-notebooks coverage complexity dependencies security maintainability
GIT_REVISION ?= $(shell git rev-parse HEAD 2>/dev/null || echo unknown)

format:
	uv run ruff format src typings

build-images:
	docker build --build-arg GIT_REVISION=$(GIT_REVISION) -f Dockerfile -t wine-quality-classification:train ../../libs/sagemaker-local/docker
	docker build --build-arg GIT_REVISION=$(GIT_REVISION) -f Dockerfile.inference -t wine-quality-classification:inference ../../libs/sagemaker-local/docker

test:
	uv run pytest -m "not integration"

test-notebooks:
	/opt/mlops-venv/bin/python -m pytest -m integration

lint:
	uv run ruff format --check src typings
	uv run ruff check src typings

type-check:
	uv run pyright src

sync:
	uv sync --all-packages

coverage:
	uv run pytest -m "not integration" --cov --cov-report=term-missing:skip-covered --cov-fail-under=85

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
	uv run semgrep --quiet --config p/default --metrics off --error .

maintainability:
	uv run xenon --max-absolute B --max-modules A --max-average A . -e "*/node_modules/*"

quality: format lint type-check coverage complexity dependencies security maintainability

# Per-service lifecycle: bring up only what the current notebook needs
# (make up-moto / up-kafka / up-flink), check status, tear down.
COMPOSE_PROJECT ?= wine-quality-classification

up-%:
	docker compose -p $(COMPOSE_PROJECT) up -d --wait $*

ps:
	docker compose -p $(COMPOSE_PROJECT) ps

down:
	docker compose -p $(COMPOSE_PROJECT) down -v
