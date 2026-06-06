PROJECT ?= nyc_taxi_demand_forecasting
CONCEPT_ID ?= bias_variance_tradeoff
QUALITY ?= preview
MANIM_IMAGE ?= manimcommunity/manim:v0.20.1
MANIM_CUSTOM_IMAGE ?= mlops-manim-prod
VIDEO_OUTPUT_DIR ?= videos/output

.SILENT:
.PHONY: install format lint type-check test test-bdd test-e2e test-videos-docker coverage complexity dependencies architecture security quality build-site preview-site render-video check-videos collect preprocess features train tune evaluate deploy monitor mlflow
SITE_CONFIG ?= site/site.yaml
SITE_OUTPUT ?= site/build

install:
	uv sync --all-packages --dev
	uv run pre-commit install

format:
	uv run ruff format --quiet .

lint:
	uv run ruff format --check --quiet .
	uv run ruff check --quiet .

type-check:
	uv run mypy

test:
	uv run pytest -m "not (playwright or docker)"

test-videos-docker: docker/manim/Dockerfile
	docker build -f docker/manim/Dockerfile -t mlops-manim-test .
	docker run --rm \
	  -v "$(CURDIR)/libs/videos/src:/app/src:ro" \
	  -v "$(CURDIR)/libs/videos/tests:/app/tests:ro" \
	  mlops-manim-test sh -lc \
	  '. /opt/venv/bin/activate && python -m pytest /app/tests/integration/ -m docker -v'

test-bdd:
	uv run pytest projects/$(PROJECT)/tests/bdd

test-e2e:
	uv run pytest libs projects -m playwright

coverage:
	uv run pytest --cov --cov-report=term-missing:skip-covered

complexity:
	tmp=$$(mktemp); \
	uv run radon cc libs projects -s -n C > $$tmp 2>&1 || { cat $$tmp; rm -f $$tmp; exit 1; }; \
	if [ -s $$tmp ]; then cat $$tmp; rm -f $$tmp; exit 1; fi; \
	rm -f $$tmp

dependencies:
	tmp=$$(mktemp); \
	for package in libs/mlops-shared libs/ssg libs/ssg-i18n libs/ssg-i18n-machine-translation libs/ssg-notebook-render libs/ssg-syntax-highlighting libs/videos projects/$(PROJECT); do \
		(cd $$package && uv run deptry .) >> $$tmp 2>&1 || { cat $$tmp; rm -f $$tmp; exit 1; }; \
	done; \
	rm -f $$tmp

architecture:
	tmp=$$(mktemp); \
	uv run lint-imports > $$tmp 2>&1 || { cat $$tmp; rm -f $$tmp; exit 1; }; \
	rm -f $$tmp

security:
	tmp=$$(mktemp); \
	uv run semgrep --quiet --config auto . > $$tmp 2>&1 || { cat $$tmp; rm -f $$tmp; exit 1; }; \
	rm -f $$tmp

quality: lint type-check test coverage complexity dependencies architecture security

mlflow:
	uv run mlflow server --backend-store-uri sqlite:///projects/$(PROJECT)/mlflow.db --default-artifact-root ./projects/$(PROJECT)/mlruns --host 127.0.0.1 --port 5000

build-site:
	uv run python -m ssg.presentation.cli build --config $(SITE_CONFIG) --output $(SITE_OUTPUT)

preview-site:
	uv run python -m ssg.presentation.cli preview --config $(SITE_CONFIG) --output $(SITE_OUTPUT)

render-video: docker/manim/Dockerfile
	docker build -f docker/manim/Dockerfile -t $(MANIM_CUSTOM_IMAGE) .
	mkdir -p $(VIDEO_OUTPUT_DIR)
	chmod 777 $(VIDEO_OUTPUT_DIR)
	docker run --rm \
	  -v "$(CURDIR)/libs/videos/src:/app/src:ro" \
	  -v "$(CURDIR)/videos/definition:/app/definition:ro" \
	  -v "$(CURDIR)/videos/output:/app/output:delegated" \
	  $(MANIM_CUSTOM_IMAGE) sh -lc \
	  '. /opt/venv/bin/activate && videos $(CONCEPT_ID) --definitions-dir /app/definition --output-dir /app/output --quality $(QUALITY)'

# --- Video quality gate ---

check-videos:
	@echo "=== Rendering all videos ==="
	for yaml in videos/definition/*.yaml; do \
	  concept=$$(basename $$yaml .yaml); \
	  $(MAKE) render-video CONCEPT_ID=$$concept; \
	done
	@echo "=== Linting video source ==="
	uv run ruff format --check --quiet libs/videos/src/videos/
	uv run ruff check --quiet libs/videos/src/videos/
	@echo "=== Type-checking video source ==="
	uv run mypy libs/videos/src/videos/ --no-error-summary
	@echo "=== Running video unit tests ==="
	uv run pytest libs/videos/tests/ -m "not docker" -v -q
	@echo "=== Running Docker visual regression tests ==="
	$(MAKE) test-videos-docker
	@echo "=== All video checks passed ==="

collect preprocess features train tune evaluate deploy monitor:
	uv run python -m $(PROJECT).interfaces.cli $@ --config projects/$(PROJECT)/configs/project.yaml
