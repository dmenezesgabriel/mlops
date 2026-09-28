# Backlog — repo-wide quality-gate parity (EPHEMERAL)

> **EPHEMERAL WORK BACKLOG — iterates freely; never cited from code.**
> Every item carries measured evidence (tool output, file:line, counts).
> DoD = `make quality` green at commit; a flipped gate lands with or after
> the fixes it requires. Sizes: S ≤ 1 day · M = 1–3 days · L = 3–5 days.

Canonical gate set (athena §8.4): ruff format+lint · pyright · pytest ·
pytest-cov · radon `cc -s -n C` · xenon `--max-absolute B --max-modules A
--max-average A` · vulture · bandit `-q -r src -ll` · semgrep `--config
auto` · deptry · import-linter. Scan scope: radon/xenon = whole package
(tests included); bandit/vulture = `src`; vendored trees excluded via each
tool's real exclusion flag.

## A. Audit & bootstrap (MQ-0)

| ID | Item | Work | Evidence | Depends |
|---|---|---|---|---|
| QG-1 | [x] Bootstrap `docs/repo-quality/` (README/milestones/backlog) seeded with the 2026-09-27 audit measurements | S | this row; audit ran live: per-package Makefile targets diffed vs §8.4, missing tools executed to size findings | — |

## B. Gate wiring (MQ-1)

| ID | Item | Work | Evidence | Depends |
|---|---|---|---|---|
| QG-2 | [ ] Fix shared radon recipe: `-x "*/node_modules/*"` → `-e "*/node_modules/*"` in 13 Makefiles. `-x` is radon's `--max` (grade bound) — the pattern value suppresses ALL output, so `make complexity` has been a silent no-op (verified: `radon cc . -s -n C -x "*/node_modules/*"` prints nothing on `videos-linter` where D25 exists; `-e` correctly excludes `ssg-latex` vendored katex while reporting real C+). Only `data-science-scaffold` (`radon cc src`) and `docker/moto` (`radon cc .`) enforce today. Whole-package scope per decision — flip lands with/after QF-1/2/3/9 fixes | S | `radon cc --help` (`-x`=--max, `-e`=--exclude); 13 Makefiles using `-x`: athena-local, mlops-shared, ssg, ssg-i18n, ssg-i18n-mt, ssg-latex, ssg-notebook-render, ssg-syntax-highlighting, diagrams, videos, videos-linter, nyc_taxi_demand_forecasting, ml_specialization | QF-1, QF-2, QF-3, QF-9 |
| QG-3 | [ ] `libs/sagemaker-local` Makefile: add `coverage`, `complexity`, `dependencies`, `security`, `maintainability` targets; `quality` chain extended. `[tool.deptry]` map already in its pyproject; `[tool.pyright]` present | S | `libs/sagemaker-local/Makefile` (5 targets vs 10); `libs/sagemaker-local/pyproject.toml:18,33` | — |
| QG-4 | [ ] `projects/sagemaker_{catboost,lightgbm,scikit_learn,xgboost}` Makefiles: add `coverage`, `complexity`, `dependencies`, `security`, `maintainability` targets. deptry `package_module_name_map`+`per_rule_ignores` already configured in each pyproject | S | `projects/sagemaker_*/Makefile` (format/lint/type-check/test/build-images/sync only); `projects/sagemaker_*/pyproject.toml:20-28` | — |
| QG-5 | [ ] Root `Makefile`: `PACKAGES` += `projects/ml_specialization` + `projects/sagemaker_*` ×4 (uv-workspace members unreachable via `make quality` today); root `quality` chain += `maintainability` | S | root `Makefile` `PACKAGES` line; `pyproject.toml` `[tool.uv.workspace].members`; `projects/ml_specialization/Makefile` already has all gate targets | QG-3, QG-4, QG-7 |
| QG-6 | [ ] `security` target repo-wide: prepend `bandit -q -r src -ll` + `vulture src` ahead of the existing `semgrep --config auto .` (docker/moto scans `glue_overlay.py` — no `src/` dir). Per-package `[tool.vulture]`: `min_confidence=80` + `ignore_names` for framework entry points (HTMLParser `handle_*`, plugin factories, `main`, typer/click callbacks) — athena's list is the template | M | `libs/athena-local/Makefile` security target + `pyproject.toml [tool.vulture]`; measured: vulture@80 = 10 findings repo-wide (see QF rows); bandit = ssg B704 ×5 | QF-4…QF-9 findings triaged per package |
| QG-7 | [ ] `maintainability` target (xenon `--max-absolute B --max-modules A --max-average A .`, `-e "*/node_modules/*"` on vendored dirs) in every package Makefile | S | `libs/athena-local/Makefile` `maintainability`; xenon `--help` `-e/--exclude`; measured whole-package errs in QF rows | QF-1…QF-5, QF-9 |
| QG-8 | [ ] import-linter: add `glue_overlay` to `root_packages` + a contract keeping `docker/moto` independent of workspace packages; add `sagemaker_local` independence contract; decide per-evidence whether `ml_specialization`/`sagemaker_*` need source-side contracts (today they appear only as forbidden targets) | S | root `pyproject.toml [tool.importlinter]` (`root_packages` omits `glue_overlay`; contracts cover ssg*/videos*/athena only) | — |
| QG-9 | [ ] `.pre-commit-config.yaml`: extend bandit/vulture/xenon beyond `files: ^libs/athena-local/` — granularity decided at execution (repo-wide entries vs per-lib `files:` scoping; vulture needs each package's `[tool.vulture]` or mirrored `--ignore-names` like the existing athena hook comment explains) | S | `.pre-commit-config.yaml` hooks block | QG-6, QG-7 |

## C. Findings (MQ-2) — worst-first, one package per item

| ID | Item | Work | Evidence | Depends |
|---|---|---|---|---|
| QF-1 | [x] `libs/videos-linter` `linter_service.py` — done 2026-09-28. `analyze_video` D25 → `analyze_video` orchestrator + `_collect_frame_stats`/`_FrameStats`/`_frame_centroid`/`_longest_frozen_run`/`_is_brightness_sign_flip`/`_first_jump_distance` + `_check_frozen`/`_check_flicker`/`_check_stutter`; `check_image` C19 → `_detect_boxes`/`_collect_channel_boxes`/`_is_known_box`/`_intersection_area`/`_overlap_violation`; `verify_visuals` 3-block dup → (checker, label) loop; `_read_image` dedupes 3× `imread`+None. Identical thresholds/rules/messages. Verified: 14 tests green, `radon cc . -n C -e` empty, `xenon .` exit 0, pyright 0 err. File 412→449 lines (<500). NOTE: IDE buffer desync observed mid-session — edits landed via buffer then disk reverted twice; final state disk-verified (md5 + gates) | M | measured 2026-09-27: `xenon .` → 5 errs; `radon cc` → same 4 blocks | — |
| QF-2 | [ ] `libs/athena-local` tests — whole-package scope exposes ~12 C+/D/E test functions + `_parity.inflate_member` C11: `test_cli_query_execution_examples` E31, `test_cli_data_catalog_examples` D23, `test_cli_workgroup_examples`/`named_query_examples` C16/C13, `_tokenize` C12, `test_data_catalog_crud_round_trip_with_botocore` C12, `_exercise_boto3_control_plane` C11, `test_read_sql_query_ctas_parquet_round_trip_live` C14, `test_every_operation_round_trips_through_botocore` C12, `test_submit_statement_posts_query_with_session_headers` C13. Table-drive/loop-split, keep assertions | M | `xenon .` → 16 errs; `radon cc . -n C` block list | — |
| QF-3 | [ ] `libs/videos` — `ManimRenderer` C11 (`infrastructure/manim/renderer.py:19`); xenon module-B `renderer.py`, `validation/geometry_rules.py`; vulture 3@80 (`ports/linter.py:16 video_path`, `manim/scene_builder.py:18 kwargs`, `validation/linter_service.py:53 video_path` — protocol-arg leftovers) | M | `xenon .` → 4 errs; `vulture --min-confidence 80 src` → 3 | — |
| QF-4 | [ ] `projects/nyc_taxi_demand_forecasting` — xenon module-B on src: `pipelines/train.py`, `pipelines/monitor.py` (no C+ blocks; module-average breaches) | S | `xenon .` → 2 errs | — |
| QF-5 | [ ] `libs/ssg` — bandit B704 ×5 (`markupsafe.Markup` on rendered HTML — triage: legitimate escaping boundary → `# nosec B704` with reason, or bandit config skip; NOT a blanket ignore) + xenon module-B `tests/unit/infrastructure/test_local_preview_server.py` | S | `bandit -q -r . -ll` → 5×B704; `xenon .` → 1 err | — |
| QF-6 | [ ] `libs/mlops-shared` — vulture 3@80: `datasets.py:15,26` unused `dataset_path`/`dataset` vars | S | `vulture --min-confidence 80 src` → 3 | — |
| QF-7 | [ ] `libs/ssg-i18n-machine-translation` — vulture 2@80 (`transformers_text_translator.py:11` `model`/`task` ctor vars); xenon module-B `tests/unit/test_evaluator.py` | S | `vulture --min-confidence 80 src` → 2; `xenon .` → 1 err | — |
| QF-8 | [ ] `libs/ssg-latex` — vendored `src/ssg_latex/node_modules/katex` needs `-e "*/node_modules/*"` (radon), `--exclude` (xenon), vulture path exclusion; own-code vulture 1@80 (`latex_processor.py:74 attrs`) | S | xenon 3 errs all under `node_modules/katex`; vulture 2@80 incl. katex `generate_fonts.py` | — |
| QF-9 | [ ] `libs/ssg-notebook-render` (xenon module-B `tests/unit/test_notebook_content_renderer.py`), `libs/sagemaker-local` (radon C11 `tests/unit/test_config.py:18`) — one test-file finding each | S | `xenon .` → 1 err each | — |
| QF-10 | [ ] Verify-clean row: `diagrams`, `ssg-i18n`, `ssg-syntax-highlighting`, `docker/moto`, `ml_specialization`, `sagemaker_*` ×4, `mlops-shared` (xenon) measured clean — wiring lands with a green re-measure recorded in the row | S | `xenon .`/`vulture@80` → 0 errs each | QG-2…QG-7 |

## D. Hardening (MQ-3) — user-approved stretch

| ID | Item | Work | Evidence | Depends |
|---|---|---|---|---|
| QH-1 | [ ] Coverage floors: measure `pytest --cov` % per package, wire `--cov-fail-under` into each Makefile `coverage` target (target ≥75 matching `libs/athena-local/Makefile`; a package below floor gets a coverage sub-item or a documented floor value with reason) | M | athena `--cov-fail-under=75`; every other package runs `--cov` with no floor today | MQ-2 |
| QH-2 | [ ] Pyright `standard`→`strict` per lib (athena QA-6 playbook: measure `typeCheckingMode=strict` error count, fix fallout package by package; root `pyproject.toml` stays `standard` for non-lib invocations). Order smallest-first; athena already strict | L | `libs/athena-local/pyproject.toml` `typeCheckingMode="strict"`; all other `[tool.pyright]` sections `standard`; athena's measured cost: 72 errors/33 kLOC | MQ-2 |

## Definition of Done (all items)

- `make quality` green at commit; the flipped/new gate demonstrably
  enforced (probe: a deliberate violation fails it — recorded in the row).
- Pure refactors keep existing tests green; behavior changes are TDD.
- Findings are fixed, or configured-out with the reason written in the
  row — no silent waivers, no `# noqa`/`nosec`-spam.
- Gate numbers (tests passed, coverage, findings closed) go in the commit
  body, never in these docs.
