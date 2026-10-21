.SILENT:
.PHONY: format lint type-check test test-docker lock-requirements coverage complexity dependencies security maintainability

format:
	uv run ruff format .

lint:
	uv run ruff format --check .
	uv run ruff check .

type-check:
	uv run pyright src

test:
	uv run pytest -m "not docker"

# The moto-backed integration tests run in `test`/`coverage`; only the
# daemon-dependent docker tests are opt-in.
test-docker:
	uv run pytest -m docker

# Regenerate the per-image hashed locks. Target: CPython 3.12, linux/amd64.
# sagemaker-training and inotify-simple are the only sdist-only runtime
# packages measured on PyPI (2026-10-21); every other one must be a wheel.
# pip applies build options in file order, so a trailing `--only-binary :all:`
# would cancel the two `--no-binary` exceptions. Train locks therefore keep
# only the exceptions; their hash set is already wheel-only for the rest.
lock-requirements:
	for input in docker/requirements/*.in; do \
		name="$${input%.in}"; \
		extra=""; \
		case "$$name" in *-inference) ;; *) extra="--no-binary sagemaker-training --no-binary inotify-simple";; esac; \
		uv pip compile --generate-hashes --emit-build-options \
			--python-version 3.12 --python-platform x86_64-manylinux_2_28 \
			--only-binary :all: $$extra "$$input" \
			--output-file "$$name.txt"; \
		case "$$name" in *-inference) ;; *) sed -i '/^--only-binary :all:$$/d' "$$name.txt";; esac; \
	done

coverage:
	uv run pytest -m "not docker" --cov --cov-report=term-missing:skip-covered --cov-fail-under=95

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
	uv run semgrep --quiet --config p/default --metrics off --error .

maintainability:
	uv run xenon --max-absolute B --max-modules A --max-average A . -e "*/node_modules/*"

quality: lint type-check coverage complexity dependencies security maintainability
