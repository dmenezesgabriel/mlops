# AX-2 — user-facing surface → scenario matrix sweep (2026-10-11)

Scope: every workspace package's *user-facing* surface — CLIs, services,
pipeline runs (`methodology.md` D10) — mapped to its pytest-bdd scenario
coverage. Includes every `→ AX-2` tag deferred by AU-01…AU-27 reports and the
AU-26b consumer-surface matrix. Exclusions per the README inventory:
`projects/notebooks` (no Python), `projects/ml_monitoring_draft` (scratch, own
`.venv`), vendored `node_modules`. Root `Makefile` recipes that only launch
external tools (`mlflow server`, `jupyterlab`) are dev infra, not package
surfaces.

Method: enumerate surfaces from `[project.scripts]`, `python -m` targets,
`add_parser`/`@app.*` decorators, and `Makefile` recipes; count scenarios per
`.feature` (`grep -c Scenario`); read the covering test where the audit
reports claimed one. Dispositions: **scenario** (pytest-bdd), **e2e/int**
(user surface exercised end-to-end with production-like seams, not
bdd-shape), **structural** (hole exists by construction), **S4** (promoted —
no layer above unit exercises the surface, with a demonstrated-escape or
unexercised-arm harm argument).

## Surface → scenario matrix

| Pkg | Surface | Invocation | Coverage | Disposition |
|---|---|---|---|---|
| athena-local | HTTP wire — `GET /health`, `POST /` dispatch, 36 implemented ops | `athena_local/main.py:164,181` | 11 `.feature` / **53 scenarios** (`tests/bdd/`, grep-counted: artifacts 5, canonical_model 3, catalog_metadata 7, data_catalogs 8, engine_versions 1, managed_results 1, named_queries 7, prepared_statements 8, query_executions 3, tags 5, workgroups 5) | scenario-covered |
| athena-local | consumer: boto3/botocore | HTTP client | 70/70 declared ops — `tests/integration/test_botocore_parity_loop.py` | covered (AU-26b) |
| athena-local | consumer: AWS CLI | real `aws` binary — `tests/integration/_cli_harness.py:218` | 28/36 implemented ops; `test_aws_cli_consumer.py:47-84` stem list | **structural** — the 8 unexercised ops (6 PreparedStatement + `ListEngineVersions` + `GetQueryRuntimeStatistics`) have no awscli-shipped example to parity-check; AU-26b: not defects |
| athena-local | consumer: terraform (Go provider) | `tests/terraform/provider_operation_shapes_test.go` | 16/36 implemented ops | **structural** — provider can't express the other 20 ops (data sources/metadata); AU-26b: not defects |
| athena-local | consumer: notebooks | `projects/athena_emulator` parity run | 0 in-package; 16 nbclient fns out-of-package | covered transitively |
| ml_specialization | `GET /predict/{location_id}` | `inference/api.py:96`; uvicorn | `tests/bdd/features/predict.feature` — 4 scenarios (200/503/404/500) | scenario-covered |
| ml_specialization | CLI 8 subcommands — collect/preprocess/features/train/tune/evaluate/deploy/monitor | `python -m ml_specialization.interfaces.cli <cmd> --config` (`interfaces/cli.py:26-31,66`; registry `cli.py:35-45`) | `tests/unit/interfaces/test_cli.py` + `test_pipeline_stubs.py` — unit only, 0 scenarios | **S4 → G-320** |
| ml_specialization | `BatchDemandPredictor.predict` | `inference/batch_predict.py:18` (class API) | `tests/unit/inference/test_batch_predict.py` — unit only | folded into G-320 |
| ml_specialization | `feast apply` on `feature_repo/` | `feast -c feature_repo apply` | zero execution coverage — `grep feast tests/` hits conftest/fakes only | folded into G-320 |
| nyc_taxi | `GET /predict/{location_id}` | `inference/api.py:95`; uvicorn | `tests/bdd/features/predict.feature` — 4 scenarios (200/503/404/500) | scenario-covered |
| nyc_taxi | CLI 8 subcommands (same registry shape) | `python -m nyc_taxi_demand_forecasting.interfaces.cli <cmd> --config` (`interfaces/cli.py:30,68`; registry `cli.py:34-45`); root `Makefile:169` + project `Makefile` recipe per command | `tests/unit/interfaces/test_cli.py` + `tests/unit/pipelines/*` — unit only, 0 scenarios | **S4 → G-321** |
| nyc_taxi | `BatchDemandPredictor`, `feast apply`+`materialize`, monitor report write | same shape as ml_spec | `tests/unit/features/test_feast_materialization.py` (faked feast) — 0 real `apply` runs | folded into G-321 |
| ssg | `build` (`--config --output [--collection]`) | `python -m ssg.infrastructure.cli build` (`cli.py:32,42,218-220`); root `Makefile:102` `build-site` | `tests/integration/test_static_site_generation.py:21` (real builder + plugins over tmp site) + `tests/playwright/test_built_site_smoke.py` (browser e2e over a real `make build-site` output); 0 `.feature` | e2e/int-covered — bdd-shape absence noted, no row |
| ssg | `preview` (`--host --port --reload-interval`) + SSE reload | `cli.py:34-38`; root `Makefile:113` `preview-site` | `tests/unit/.../test_site_preview.py` + `test_local_preview_server.py` + `test_main_preview_rebuild_renders_edited_page` (fake reloader/server) — the assembled edit→rebuild→serve loop has fakes on both seams; one *manual* live run (`e2e-verification.md:25`); 0 scenarios | **S4 → G-316** |
| ssg | `--collection` select | `cli.py:220` | unit pins post-AF-35 (incl. `site.py:40`); no scenario | folded into G-316 |
| ssg-syntax-highlighting | `language-*` code blocks via `ssg build` (`ssg.html_post_processors` EP) | transitive | unit `process()` + playwright `_assert_notebook_and_code_pages` | folded — rides `build` |
| ssg-latex | math rendering via `ssg build` | transitive | unit `process()`; playwright built site | folded — rides `build` |
| ssg-notebook-render | `.ipynb` page builds (`ssg.renderers` EP) | transitive | unit; playwright notebook page; `test_static_site_generation` asserts nb content | folded — rides `build` |
| ssg-i18n | i18n site variants (`ssg.site_variant_providers` EP) | transitive via `ssg build` | `tests/integration/test_i18n_static_site_generation.py:24` e2e (real builder + `InMemoryTextTranslator`) + playwright `_assert_language_switcher` | e2e/int-covered — no row |
| ssg-i18n-mt | `ssg-i18n-evaluate` CLI | `[project.scripts]`; root `Makefile:105` `evaluate-translation` | `tests/unit/test_cli.py` post-AF-64 (rc=1/FAILURES/BLEU pins) — 0 scenarios over real dirs | **S4 → G-317** |
| ssg-i18n-mt | transformers translator EP (`ssg_i18n.text_translators`) | plugin load via ssg-i18n | unit pins (AF-58/64); **transformers path unexercised end-to-end** — host/gate lack the `[transformers]` extra (`e2e-verification.md:58`) | folded into G-317 |
| videos | `videos <concept_id> [--definitions-dir --output-dir --quality]` | `[project.scripts]`; dockerized `Makefile:115` `render-video`, `:130` `check-videos` | real-argv `tests/unit/.../test_cli.py` (AF-77) + `tests/integration/videos/e2e/test_full_pipeline.py` (drives `Director.produce`, not argv); real renders docker-gated/manual — 0 scenarios over the command | **S4 → G-319** |
| videos-linter | `verify_visuals`/`verify_video` inside `produce()`; `check-videos` lints *source* | library seam | flat `tests/` unit suite; artifact-lint seam reached only by the manual e2e sweep — G-185's cv2 IndexError killed a real produce there | folded into G-319 |
| sagemaker-local | `make_local_pipeline_session`/`config_from_env`/`cleanup_stale_*`/`build_image` | library API | `tests/integration/test_session_moto.py`, `test_images_docker.py` (docker-marked); transitively by sagemaker_* notebooks | e2e/int-covered — no row |
| sagemaker-local | serve_app container endpoints `/ping` `/execution-parameters` `/invocations` | `docker/serve_app.py:105,110,127` | unit request-path pins (AF-86) + `batch_transform.ipynb` → 20 real gunicorn predictions (`e2e-verification.md:22`) | covered transitively |
| sagemaker_* ×4 | `train.py` `__main__` entry | `src/*/train.py:69-90` `main()` | `tests/test_notebooks.py` nbclient `training.ipynb`/`batch_transform.ipynb`/`pipeline.ipynb` (integration-marked, `make test-notebooks`) + `test_train.py` | e2e/int-covered — no row |
| data-science-scaffold | `python -m data_science_scaffold.{scaffold,register}` | `Makefile:22-23` `make scaffold` | `tests/integration/test_scaffold.py` renders a project + runs its gates | e2e/int-covered — no row |
| data-science-scaffold | generated project's own bdd skeleton | template `tests/bdd/features/predict.feature` | ships **1 scenario** (happy path); both live siblings carry **4** (503/404/500 error arms) — the generated project's `feast apply`/CLI surfaces additionally inherit all of G-320's gaps | **S4 → G-322** |
| glue_overlay | moto Glue wire HTTP surface | compose `moto` service | `tests/test_glue_overlay.py` — 44 wire-level boto3-through-dispatch tests + CS-2b3 live-stack consumer tests (AU-03) | e2e/int-covered — no row |
| athena_emulator | parity-notebook execution | `pytest tests/test_notebooks.py -m integration` | the surface *is* the harness — parametrized nbclient runs over `notebooks/*.ipynb` against the live stack, executed files committed as evidence | covered (self-evidencing) |
| mlops-shared | — | leaf library | consumed by both projects' predict.feature transitively | N/A — no user surface |

## Evidence notes

- **Scenario counts** (grep `Scenario` per `.feature`, this session):
  athena-local 53 across 11 files; ml_spec 4; nyc_taxi 4; scaffold template 1.
  No other `tests/bdd/` or `*.feature` exists in any audited package.
- **G-316 harm**: G-28 (S1) — preview `on_change` rebuilt nothing for the whole
  AU-04 cycle because no layer exercised the assembled loop; the automated pin
  that now exists drives `main()` with fake reloader *and* fake server
  (`test_cli.py`/`test_site_preview.py`). `--collection`'s only behavioral
  checks are unit-level `navigation_for` pins.
- **G-317 harm**: AU-10's evaluator false-PASS family (S1 — PASSED on
  missing/absent/divergent input) lived on exactly this surface; current
  coverage is unit-only, and the `[transformers]` path has never executed
  end-to-end on this host (`e2e-verification.md:58` — manual-mode build only).
- **G-319 harm**: G-185 (S1, cv2 5.0 `convexityDefects` IndexError) killed all
  9 bias-variance scene produces and was found only by the manual
  e2e-verification sweep — the scenario layer that would have caught it in CI
  does not exist.
- **G-320/G-321 harm**: `/predict` is the only one of ~11 surfaces with
  scenario coverage; `feast apply` on `feature_repo/` has zero execution
  coverage in either project (AU-18's `apply(repoB)`-gets-repoA defect class
  lived on this surface, fixed but never exercised end-to-end); the 8 stub
  `run()`s now raise `NotImplementedError` — itself scenario-pin-able as a
  clean named-error exit.
- **G-322 harm**: measured drift — template ships 1 scenario, both live
  projects carry 4; the 3 error-arm scenarios (503/404/500) were gained
  post-generation and never back-ported, so the next generated project
  re-inherits the thinner surface map. Same re-injection class as AX-1's 8
  template rows.
- **athena-local consumer holes**: carried as *structural*, not rows —
  awscli ships no example for the 8 unexercised ops (nothing to parity-check
  against), and the Go provider test file exercises the 16 ops the provider
  can express; both were measured "not defects" at AU-26b and the wire
  surface itself is scenario-covered.

## Gaps promoted

| Gap ID | Pkg | Severity | One-line |
|---|---|---|---|
| G-316 | ssg | S4 | `preview` edit→rebuild→serve loop + `--collection` select have no scenario coverage — only fake-seam unit pins + one manual run; `build` is e2e/playwright-covered |
| G-317 | ssg-i18n-mt | S4 | `ssg-i18n-evaluate` CLI + transformers translator EP path: unit-only; transformers chain never run end-to-end |
| G-318 | diagrams | S4 | `diagrams-cli` has unit pins only — no scenario over real definitions; container render verified once, manually |
| G-319 | videos (+videos-linter seam) | S4 | `videos` CLI/`--quality`/`check-videos` loop: no scenario over the user command; the artifact-lint seam is where G-185 (S1) escaped to manual e2e |
| G-320 | ml_specialization | S4 | 8 CLI subcommands + `BatchDemandPredictor` + `feast apply` on `feature_repo/` — 0 scenarios (`/predict` covered 4/4) |
| G-321 | nyc_taxi | S4 | same surface set + monitor report write — 0 scenarios |
| G-322 | data-science-scaffold | S4 | template `predict.feature` ships 1 scenario vs live 4 — generated projects lose the error-arm coverage |

## Tail

- Sweep ran read-only — this diff touches only `docs/`.
- Convention note: "no `.feature`" is not itself a defect where the surface is
  exercised end-to-end with production-like seams (ssg build, sagemaker_*
  notebooks, glue_overlay wire tests, emulator harness) — those rows are
  dispositioned covered, and the promoted S4s are the surfaces where *no* layer
  above unit sees the user-facing behavior. If the project wants literal
  pytest-bdd on every package anyway, that's one policy call, not six rows.
- Next: **MA-8 remediation** — promote the 20 open register rows
  (G-303…G-322) to `AF-*` items and ship them, then **AX-3** close-out.
