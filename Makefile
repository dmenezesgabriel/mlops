PROJECT ?= nyc_taxi_demand_forecasting
CONCEPT_ID ?= bias_variance_tradeoff
QUALITY ?= preview
MANIM_IMAGE ?= manimcommunity/manim:v0.20.1
MANIM_CUSTOM_IMAGE ?= mlops-manim-prod
VIDEO_OUTPUT_DIR ?= videos/output

.SILENT:
.PHONY: install format lint type-check test test-bdd test-e2e test-videos-docker coverage complexity dependencies architecture security quality build-site preview-site render-video check-videos diagrams-build diagrams-render collect preprocess features train tune evaluate deploy monitor mlflow
SITE_CONFIG ?= site/site.yaml
SITE_OUTPUT ?= site/build

install:
	uv sync --all-packages --dev --extra notebooks
	uv run pre-commit install

PACKAGES = libs/mlops-shared libs/ssg libs/ssg-i18n libs/ssg-i18n-machine-translation libs/ssg-notebook-render libs/ssg-syntax-highlighting libs/ssg-latex libs/videos libs/diagrams projects/$(PROJECT)

format:
	for package in $(PACKAGES); do \
		$(MAKE) -C $$package format; \
	done

lint:
	for package in $(PACKAGES); do \
		$(MAKE) -C $$package lint; \
	done

type-check:
	for package in $(PACKAGES); do \
		$(MAKE) -C $$package type-check; \
	done

test:
	for package in $(PACKAGES); do \
		$(MAKE) -C $$package test; \
	done

test-videos-docker: libs/videos/Dockerfile
	docker build -f libs/videos/Dockerfile -t mlops-manim-test libs/videos
	docker run --rm \
	  -v "$(CURDIR)/libs/videos/src:/app/src:ro" \
	  -v "$(CURDIR)/libs/videos/tests:/app/tests:ro" \
	  mlops-manim-test sh -lc \
	  '. /opt/venv/bin/activate && python -m pytest /app/tests/integration/ -m docker -q -ra --tb=short'

test-bdd:
	uv run pytest projects/$(PROJECT)/tests/bdd

test-e2e:
	$(MAKE) -C libs/ssg test-e2e

coverage:
	for package in $(PACKAGES); do \
		$(MAKE) -C $$package coverage; \
	done

complexity:
	for package in $(PACKAGES); do \
		$(MAKE) -C $$package complexity; \
	done

dependencies:
	for package in $(PACKAGES); do \
		$(MAKE) -C $$package dependencies; \
	done

architecture:
	tmp=$$(mktemp); \
	uv run lint-imports > $$tmp 2>&1 || { cat $$tmp; rm -f $$tmp; exit 1; }; \
	rm -f $$tmp

security:
	for package in $(PACKAGES); do \
		$(MAKE) -C $$package security; \
	done

quality: lint type-check test coverage complexity dependencies architecture security

mlflow:
	uv run mlflow server --backend-store-uri sqlite:///projects/$(PROJECT)/mlflow.db --default-artifact-root ./projects/$(PROJECT)/mlruns --host 127.0.0.1 --port 5000

build-site:
	uv run python -m ssg.presentation.cli build --config $(SITE_CONFIG) --output $(SITE_OUTPUT)

preview-site:
	uv run python -m ssg.presentation.cli preview --config $(SITE_CONFIG) --output $(SITE_OUTPUT)

render-video: libs/videos/Dockerfile
	docker build -f libs/videos/Dockerfile -t $(MANIM_CUSTOM_IMAGE) libs/videos
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
	uv run pytest libs/videos/tests/ -m "not docker" -q -ra --tb=short
	@echo "=== Running Docker visual regression tests ==="
	$(MAKE) test-videos-docker
	@echo "=== All video checks passed ==="

diagrams-build: libs/diagrams/Dockerfile
	docker build $(DOCKER_BUILD_FLAGS) -f libs/diagrams/Dockerfile -t mlops-diagrams-prod libs/diagrams

diagrams-render:
	mkdir -p diagrams/output
	chmod 777 diagrams/output
	docker run --rm \
	  -v "$(CURDIR)/libs/diagrams/src:/app/src:ro" \
	  -v "$(CURDIR)/diagrams/definition:/app/definition:ro" \
	  -v "$(CURDIR)/diagrams/output:/app/output:delegated" \
	  mlops-diagrams-prod diagrams-cli mlops_lifecycle --definitions-dir /app/definition --output-dir /app/output

render-diagram: diagrams-build
	$(MAKE) diagrams-render

test-diagrams-docker: libs/diagrams/Dockerfile
	docker build $(DOCKER_BUILD_FLAGS) -f libs/diagrams/Dockerfile -t mlops-diagrams-test libs/diagrams
	docker run --rm \
	  -v "$(CURDIR)/libs/diagrams/src:/app/src:ro" \
	  -v "$(CURDIR)/libs/diagrams/tests:/app/tests:ro" \
	  mlops-diagrams-test pytest /app/tests/ -q -ra --tb=short

collect preprocess features train tune evaluate deploy monitor:
	uv run python -m $(PROJECT).interfaces.cli $@ --config projects/$(PROJECT)/configs/project.yaml

