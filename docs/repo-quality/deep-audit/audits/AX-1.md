# AX-1 — cross-cutting pattern sweep (2026-10-11)

Scope: every defect *pattern* flagged ≥2× across AU-01…AU-27 (+ `G-NN class`
cross-references and deferred `→ AX-1` dispositions), verified repo-wide with
scoped greps. Scope exclusions per the README inventory:
`projects/ml_monitoring_draft` (scratch, own `.venv`), `projects/notebooks`
(no Python), vendored code (`**/node_modules/**`), `__pycache__`/`.mypy_cache`/
`.venv` build artifacts.

Method: one row per pattern — the audit refs that flagged it, the probe run,
the repo-wide result, residual instances (if any), and the disposition.
Residual rows cite the *twin's* measured evidence: the residual files carry
the pre-fix construct verbatim, so the harm measured in AU-17/AU-18 (+ MA
remediation fix sessions) transfers unchanged.

## Sweep table

| # | Pattern (refs) | Probe | Repo-wide result | Residual | Disposition |
|---|---|---|---|---|---|
| 1 | Coverage pollution — bare `--cov`, no `[tool.coverage.run]`, editable workspace deps traced (G-68/G-78/G-101/G-114/G-149/G-170/G-208 — 6 shipped + 1 live) | per-package `[tool.uv.sources] {workspace=true}` dep-map × `[tool.coverage.run]` presence × `--cov-fail-under`; scoped `--cov` run | All dep-having packages scoped except **ssg** (ws-sources ssg-i18n, ssg-i18n-mt, ssg-syntax-highlighting, ssg-latex; no `coverage.run`, floor 75). Measured this session: `pytest tests/integration/test_static_site_generation.py --cov` traces `ssg_notebook_render` (217 stmts @78-80%) + `ssg_syntax_highlighting` (154 stmts @84-86%) into a 1217-stmt TOTAL. Dep-free packages (athena-local, diagrams, mlops-shared, docker/moto) cannot pollute; `sagemaker_*`×4 declare `sagemaker-local` but never import it (0 hits src+tests) — AU-16's verdict reproduces | ssg — **7th occurrence** | **G-303** |
| 2 | `str()`-coercion of loaded YAML keys/values (G-06/G-16/G-44/45/G-88/97/100/G-120/G-199/G-215 — 8 shipped) | `grep str(` across every loader/config path | Clean — all named sites shipped `_require_string_key`-style rejection; surviving `str(` uses are legit (`str(file_path)` error arg, `str(path)` logging/schedule API, `str(PROJECT_DIR)` hash input, env-var `int(raw)` parsing). `glue_overlay.py:278 str(...).upper()!="ICEBERG"` is comparison-only — non-str input can never mark a table iceberg; no stored value | none | resolved |
| 3 | `include:` stub configs (G-206/G-218 — live copies deleted AF-100/AF-104; template deferred "no gap row → AX-1") | `grep -rln 'include: project.yaml'` | 4 files remain in the scaffold template — the only copies left in the repo | template `configs/{train,evaluate,predict,materialize}.yaml` | **G-304** |
| 4 | Numeric guards accept `bool` (G-200/G-216 — live fixed AF-100/AF-104) | `grep isinstance` in `configuration.py` guards | template `_integer:231`, `_float:240`, `_integer_list:249` use bare `isinstance(value, int)` — `True` passes (`test_size: on`→`float(True)`=1.0, `months: [on]`→`(True,)`) | template `configuration.py:229-258` | **G-305** |
| 5 | `parent.parent`/`parents[N]` root anchoring (G-201/G-217 — live fixed via `configs/`-dir requirement) | `grep parent` in config loaders | template `configuration.py:88` `config_path.parent.parent.resolve()` with no `configs/`-dir membership check — loading a config outside `configs/` resolves every relative path against the wrong root. (Live `api.py` `parents[3]` kept post-fix — conforms once `load()` requires `configs/`.) | template `configuration.py:88` | **G-306** |
| 6 | `main()`/CLI traceback exits (G-17/G-40/G-88/G-109/G-151/G-203/G-222 — shipped per-package) | enumerate every `main()`/`cli` catch | template `interfaces/cli.py:68-74` `main()` calls `run_command` bare — `run_command:60` logs+re-raises, so every config error exits as a raw traceback. Live `main()`s all carry the AF-11/AF-29 catch tuple | template `interfaces/cli.py` | **G-307** |
| 7 | `split` unbounded `test_size` + `int()`-truncated holdout (G-205/G-223 — live fixed via ceil-holdout + named rejects) | `grep split/test_size` | template `models/training.py:14` `split_index = max(1, int(len(dataset) * (1 - test_size)))` — the pre-fix formula verbatim: `test_size` 0/1.5/−0.1 all accepted, `int()` shrink vs `ceil` | template `models/training.py:14` | **G-308** |
| 8 | Ambient `MlflowClient()` / `MlflowDemandModelRegistry` copies (G-207/G-214 + G-231 disposition: "template + ml_specialization copies… → AX-1 candidate") | `grep MlflowClient\|promote_champion` + consumer grep | template `models/registry.py:12` `mlflow.MlflowClient()` — ambient (cwd `mlflow.db` writes) AND zero consumers anywhere (no caller, no test). ml_specialization copy is config-injected (G-207 fixed) but `promote_champion` still has zero src consumers — only `tests/unit/models/test_registry.py` touches it | template `registry.py` + `ml_specialization/models/registry.py` | **G-309** |
| 9 | api import-time eager init + `except Exception:` swallow + `detail={exc}` echo + `features[...]` outside guard (G-196/197/198/G-219/220/221 — live fixed via lazy `_ServingResources`) | `grep except\|detail\|pickup_count` + reading | template `inference/api.py` verbatim pre-fix: module-level config load `parents[3]` (:18-20), `set_tracking_uri` global mutation (:23), `load_model` at import; `except Exception: _model = None` (:26-29) silent swallow; `detail=f"…{exc}"` echo (:71); `features["pickup_count"].iloc[0]` at :74 outside the :66-71 fetch guard → KeyError → raw 500 | template `inference/api.py` | **G-310** |
| 10 | `hourly_pickup_demand`/feature-column literal duplication (G-232 — nyc_taxi single-sourced AF-111; note explicitly defers template + ml_spec) | `grep hourly_pickup_demand\|_feature_columns\|FEATURE_COLUMNS` | template: `api.py:39-44` `feature_refs` literal + `:80-87` `feature_cols` literal, `batch_predict.py:14` `_feature_columns`; `features/hourly_demand.py` is the pre-AF-111 shape (verbatim-copy builder, no contract constants). ml_spec: `api.py:23-29,76` `_FEATURE_COLUMNS` + f-string refs, `batch_predict.py:14`, `test_api.py`, `feature_repo/feature_views.py`; `features/hourly_demand.py` is a `NotImplementedError` stub — no constants to import | template `api.py`/`batch_predict.py`/`hourly_demand.py` + ml_spec `api.py`/`batch_predict.py` (+ `feature_views` pin) | **G-311** |
| 11 | Pipeline `run()`s log "completed" with zero work + fabricating domain classes (G-204 — ml_spec fixed via `NotImplementedError`) | `grep _pipeline_completed\|NotImplementedError` | all 8 template `pipelines/*.py:15` log `"*_pipeline_completed"` after config-load only; the fabricating classes are all present (collection/preprocessing/supervised_dataset verbatim-copy shapes, `feast_materialization` mkdir-as-apply, `tuning` `return 1.0`, `hourly_demand` input→output copy, `batch_predict` predict-on-any-frame) | template `pipelines/*.py` ×8 + domain classes | **G-312** |
| 12 | unit→integration import direction (AU-26a D10 suspect — deferred "relocate at AX-1") | `grep integration._cli_examples` | `tests/unit/test_cli_examples.py:13` `from tests.integration._cli_examples import extract_command_tokens` still live; helper's consumers stay in integration (`test_aws_cli_consumer.py:28`, `test_aws_cli_query_executions.py:13`) | `libs/athena-local/tests/unit/test_cli_examples.py:13` | **G-313** |
| 13 | Private-attr pinning (G-293/G-296 — repointed via `wait_for`/`runner_task`/factory-spy seams) | `grep \._\w` asserts × deep chains | residual pins survive: `executor._semaphore._value` ×2 (`test_main.py:169,179`) — same class as `_tasks` (rename probe fails them); `wr.athena._utils._get_workgroup_config` ×3 (`test_workgroups.py:148,170`, `test_managed_results.py:167`) — third-party-private variant (wr-internal seam, breaks on upstream rename); ssg `tracker._dependencies` (`test_in_memory_dependency_tracker.py:55`) — private store where `affected_pages` is the public seam. sagemaker-local's 19 hits are its *designed* seam — `patches.py`'s private helpers are the unit under test (AF-86 shape) | athena-local ×5, ssg ×1 | **G-314, G-315** |
| 14 | `hasattr` on port-declared members (G-31/G-125 + AU-12 session note — sweep pattern) | `grep hasattr(` src-wide | Clean — 0 hits outside vendored `ssg_latex/node_modules/katex` | none | resolved |
| 15 | ClassVar mutable state (G-141/G-142/G-152 + backlog example) | `grep ClassVar` src-wide | Clean — only `athena_local/errors.py:26-27` immutable `ClassVar[str]`/`[int]` constants | none | resolved |
| 16 | Silent `except`/swallow (backlog example; G-196/219/270/283/298) | classify all `except Exception` + `except…: pass` src sites | Clean — all 12 live `except Exception` sites are shipped boundary catches (shaped `InternalServerException`/`RuntimeError`/`HTTPException`/`ValueError` or `logger.exception`+reraise); `local_preview_server.py:37` `except (BrokenPipeError, queue.Empty): pass` is a bounded SSE-disconnect arm; `watchdog_site_reloader.py:73` logs `exc_info`. The template api.py swallow folds into row 9 | none live | resolved |
| 17 | NextToken `int()` leniency (G-248/G-280 — both shipped) | `grep int(.*token` | `pagination.py:21-38` is the post-fix shape — `_TOKEN_PATTERN` fullmatch `^(0|[1-9][0-9]*)$` before `int()`, comment cites the lenient forms; sole `int(next_token)` site | none | resolved |
| 18 | Member-constraint bounds unenforced (G-249/G-252/G-256/G-257/G-271/G-272/G-273 — athena-local planes) | — | Package-scoped class; every plane's op-layer enforcement shipped in MA-7 (AF-121…AF-155) | none | resolved |
| 19 | Comment-blind SQL lexers (G-261/G-264/G-277 — 3 sites) | — | All three planes shipped (AF-128/AF-136/AF-139) | none | resolved |
| 20 | Verbatim-copy drift (notebook renderer clone G-72-74, `boundary_helpers` ×3 G-289, `sagemaker_*` ×4 clones) | — | All shipped (AF-47/AF-143; AU-16 batch fix); no other verbatim copies were ever flagged | none | resolved |
| 21 | `py.typed` absence (G-165 class) | `find -name py.typed` | Clean — all 20 packages + the scaffold template ship it | none | resolved |
| 22 | Gate-parity drift (G-13/G-14) | — | Pinned by AF-07's `test_generated_project_gates_match_live_shape` — drift now fails the scaffold suite | none | resolved |
| 23 | MagicMock vs named fakes (ADR-0005; G-149/G-170/G-209 — 3×) | `grep MagicMock\|mock.patch\|@patch` tests-wide | Clean — 2 hits are docstrings in named-fake modules (`_fakes.py`, `_diagrams_fakes.py`); 1 real site: `videos/tests/integration/.../test_renderer.py:116` `patch("tempfile.TemporaryDirectory", side_effect=spy)` — a spy on a stdlib seam, not an attribute-bag fake; ml_spec has 0 real hits (filename match only) | none (1 borderline spy noted) | resolved |
| 24 | `import_module`/lazy-import boundary seams — deferred import for heavy deps (related shape to row 8's `import_module("mlflow.client")`) | reading | ml_spec `registry.py:21` + `batch_predict.py` use `import_module` lazily — honest seam (mlflow import cost deferred); no defect | none | noted, no row |

## Residual evidence

- **Row 1 (G-303)**: `libs/ssg` — plugins installed editable in
  `libs/ssg/.venv` (`_editable_impl_ssg_*.pth` ×5 present) and imported by
  `tests/integration/test_static_site_generation.py:12-15`; scoped `--cov`
  run this session lists `ssg_notebook_render` 217 stmts @78-80% +
  `ssg_syntax_highlighting` 154 stmts @84-86% inside a 1217-stmt TOTAL —
  foreign stmts diluting the denominator, floor 75 below the sibling-95
  convention.
- **Rows 3-11 (G-304…G-312)**: the scaffold template carries the measured
  pre-fix construct verbatim. Every twin probe was executed against this
  identical code in `projects/ml_specialization` / `nyc_taxi` (AU-17/AU-18 §D1
  tables; AF-100/AF-104 RED probes) — the constructs are byte-level matches:
  `split` formula, `isinstance(value, int)` guards, `parent.parent` anchor,
  bare `main()`, `*_pipeline_completed` logs, `except Exception: _model=None`.
  Harm transfers without re-measurement; a generated project re-inherits
  every fixed class.
- **Row 12 (G-313)**: import edge read directly — no measurement needed
  beyond the live `from tests.integration._cli_examples import` at :13.
- **Rows 13 (G-314/G-315)**: class already measured by G-293/G-296's
  rename-probes (faithful rename → assert failures). The residual sites pin
  the same shape: `_semaphore._value` fails under a `_semaphore`→
  `_concurrency_gate` rename; `tracker._dependencies` under a store rename.

## Gaps promoted

| Gap ID | Pkg | Severity | One-line |
|---|---|---|---|
| G-303 | ssg | S3 | coverage pollution — editable `ssg-notebook-render`/`ssg-syntax-highlighting` traced into TOTAL (7th occurrence); no `[tool.coverage.run]`, floor 75 |
| G-304 | data-science-scaffold | S3 | template `configs/{train,evaluate,predict,materialize}.yaml` `include:` stubs — the last `include:` copies in the repo |
| G-305 | data-science-scaffold | S3 | template `configuration.py` numeric guards accept `bool` (`test_size: on`→1.0, `months: [on]`→`(True,)`) — G-200/216 class |
| G-306 | data-science-scaffold | S3 | template `configuration.py:88` `parent.parent` anchor without `configs/`-dir requirement — wrong-root resolution (G-201/217 class) |
| G-307 | data-science-scaffold | S3 | template `interfaces/cli.py` `main()` no catch → raw tracebacks (G-17 class) |
| G-308 | data-science-scaffold | S3 | template `models/training.py:14` unbounded `split` + `int()` truncation (G-205/223 class) |
| G-309 | data-science-scaffold + ml_specialization | S3 | `MlflowDemandModelRegistry`/`promote_champion` zero src consumers in both copies; template's `MlflowClient()` ambient (G-231/G-207 classes) |
| G-310 | data-science-scaffold | S3 | template `inference/api.py` pre-fix bundle — eager init, `except Exception` swallow, `detail={exc}` echo, `pickup_count` outside guard (G-196/197/198 class) |
| G-311 | data-science-scaffold + ml_specialization | S3 | `hourly_pickup_demand`/feature-column literals deferred by AF-111 — template + ml_spec `api`/`batch_predict` (G-232 class) |
| G-312 | data-science-scaffold | S3 | all 8 template `pipelines/*.py` `run()`s log `*_pipeline_completed` with zero work + fabricating domain classes (G-204 class) |
| G-313 | athena-local | S3 | `tests/unit/test_cli_examples.py:13` imports `tests.integration._cli_examples` — unit suite depends on integration-owned helper (deferred at AU-26a) |
| G-314 | athena-local | S4 | residual private-attr pins — `executor._semaphore._value` ×2, `wr.athena._utils._get_workgroup_config` ×3 (G-293/296 class) |
| G-315 | ssg | S4 | `test_in_memory_dependency_tracker.py:55` asserts `tracker._dependencies` private store — `affected_pages` public seam exists (G-293 class) |

## Tail

- Sweep ran read-only on `src/`/`tests/` — this diff touches only `docs/`.
- Every pattern carries a probe command + result, not vibes (protocol §5);
  the two borderline notes (videos tempfile spy, `import_module` seams) are
  inspected and dispositioned, not left as suspects.
- The dominant residual theme is **template drift**: AU-17's tail already
  warned that fixes don't propagate either direction — 8 of 13 new rows are
  `data-science-scaffold` template sites that will re-inject fixed defect
  classes into the next generated project.
- New `AF-*` items are NOT created here — the register rows promote during
  MA-8's remediation step (after AX-2), per the milestone's own scheduling.
- Next: **AX-2** — user-facing surface → bdd scenario matrix (all audits
  done; tagged surfaces: `ssg build`/`preview`/`--collection`, `videos` CLI,
  `ssg-i18n-evaluate`, `.ipynb`-build, `diagrams-cli`, i18n variants,
  ml_spec/nyc_taxi CLIs + `/predict` + `feast apply`, athena-local CLI/Go
  gaps 8+20).
