.SILENT:
.PHONY: format lint type-check quality sync build-images test test-notebooks

format:
	uv run ruff format src

build-images:
	docker build -f Dockerfile -t sagemaker-catboost:train ../../libs/sagemaker-local/docker
	docker build -f Dockerfile.inference -t sagemaker-catboost:inference ../../libs/sagemaker-local/docker

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

quality: format lint type-check test
