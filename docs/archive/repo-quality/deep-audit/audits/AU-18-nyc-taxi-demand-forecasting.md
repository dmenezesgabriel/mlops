# AU-18 — nyc_taxi_demand_forecasting audit (2026-10-05)

Package: `projects/nyc_taxi_demand_forecasting` — 1570 src LOC / 1215 SLOC
(radon raw), 28 modules, 71 unit tests + 1 pytest-bdd scenario, own-tree
coverage 100% over 1483 stmts (floor 95, `source=["src","tests"]` already
scoped — backlog's QH-5 note holds). This is the template's *real* form —
the sibling AU-17 audited the same skeleton with stub bodies.

## Surface inventory

| Module | LOC | Public symbols |
|---|---|---|
| `interfaces/cli.py` | 76 | `create_parser`, `create_registry`, `run_command`, `main`* |
| `pipelines/{collect,preprocess,features,train,tune,evaluate,deploy,monitor}.py` | 13–191 | `run`* ×8 (CLI entry points) |
| `configuration.py` | 222 | `ProjectPaths/Collection/Feature/Mlflow/Training/Evaluation/Feast/ProjectConfig`, `ProjectConfigLoader.load` |
| `data/collection.py` | 37 | `TlcYellowTaxiParquetCollector.collect` |
| `data/preprocessing.py` | 59 | `YellowTaxiTripPreprocessor.preprocess`/`clean` |
| `data/supervised_dataset.py` | 55 | `NextHourDemandDatasetBuilder.build`/`build_from_trips` |
| `features/hourly_demand.py` | 33 | `HourlyDemandFeatureBuilder.build`/`build_from_dataset` |
| `features/feast_materialization.py` | 30 | `LocalFeastMaterializer.apply` |
| `models/training.py` | 241 | `DemandRegressor`(proto), `Median/Linear/RidgeDemandRegressor`, `PyfuncDemandModel`, `DemandDatasetSplitter`, `DemandModelTrainer.train`* |
| `models/tuning.py` | 163 | `TuningResult`, `DemandModelTuner.select_best` |
| `models/registry.py` | 18 | `MlflowDemandModelRegistry.registered_model_name` |
| `inference/api.py` | 98 | `app`*, `fetch_online_features`, `predict_demand`* (`GET /predict/{id}`) |
| `inference/batch_predict.py` | 34 | `BatchDemandPredictor.predict` |
| `evaluation/metrics.py` | 6 | re-export shim (real consumer `models/training.py:17`) |

Non-src adjacent: `feature_repo/{entities,data_sources,feature_views}.py`
(feast repo definitions; `feature_views.py` bare-imports `entities`/
`data_sources`, relying on sys.path injection), `configs/*.yaml`.

## Callgraph

```
cli.main → MlopsLoggingConfigurator.configure → create_registry → run_command
  → collect.run → ProjectConfigLoader.load → TlcYellowTaxiParquetCollector.collect
      → requests.get → write_bytes
  → preprocess.run → YellowTaxiTripPreprocessor.preprocess → glob→concat→clean→to_parquet
  → features.run → NextHourDemandDatasetBuilder.build → HourlyDemandFeatureBuilder.build
      → LocalFeastMaterializer.apply → import_module("feast"/"entities"/"feature_views")
      → FeatureStore(repo_path).materialize(start,end)      [window = config year/months]
  → train.run → _resolve_best_alpha → mlflow.{set_tracking_uri,get_experiment_by_name,search_runs}
      → DemandModelTrainer.train → read_parquet → import_module("feast").get_historical_features
      → DemandDatasetSplitter.split → RidgeDemandRegressor.fit → predict
      → RegressionMetricCalculator.calculate → _log_model → mlflow.* (set_uri/start_run/log_*)
  → tune.run → DemandModelTuner.select_best → _load_entity_df → _fetch_features
      → split → optuna.create_study.optimize (25 nested mlflow runs) → TuningResult
  → evaluate.run → read_parquet → FeatureStore (run-local import) → get_historical_features
      → split → MlflowClient().get_latest_versions → pyfunc.load_model → predict
      → calculate → set_model_version_tag ×3 → require_within   [tags BEFORE gate]
  → deploy.run → MlflowClient().get_latest_versions → set_registered_model_alias
  → monitor.run → read_parquet → MlflowClient → _load_champion_model (except Exception→latest)
      → model.predict (cast pd.Series) → calculate → _pickup_drift_stats → write monitoring.md
api predict_demand → [import-time: load(config) + FeatureStore + set_tracking_uri + load_model]
  → fetch_online_features → _store.get_online_features → _model.predict → normalize
BatchDemandPredictor.predict → import_module("mlflow") → load_model → predict → to_parquet
```

Unreachable-looking code: `MedianDemandRegressor`, `LinearDemandRegressor`,
`MlflowDemandModelRegistry` — zero production consumers (tests only);
`evaluate.py:52`/`deploy.py:20`/`monitor.py:31` "no model" arms dead for
missing models (real client raises `MlflowException` first — see D9 note).

## Boundary table

| Boundary | Where | Faked as | Test |
|---|---|---|---|
| `requests.get` (60s, full-buffer `.content`) | collection.py:30-33 | `FakeRequestsModule` module-swap | test_collection.py ✓ |
| feast `FeatureStore` | features.py:5 (top-level) · evaluate.py:27 (in-run) · training.py:185/tuning.py:84/feast_materialization.py:13 (`import_module`) | `FakeFeatureStore` via monkeypatch/`import_module_for` | ✓ (3 inconsistent seam styles) |
| feast repo modules (`entities`,`feature_views`) | feast_materialization.py:22-23 + sys.path.insert :17 | `import_module_for` mapping — real import never tested | divergence → G-229 |
| `mlflow` module (set_uri/set_experiment/start_run/log_*/search_runs/pyfunc) | api.py:23-27, registry.py:14, train.py:13-41, training.py:224-237, tuning.py:101-128, evaluate.py:47, monitor.py:63 | `FakeMlflowModule` attr-swap | ✓ |
| `MlflowClient` (versions/alias/tags) | deploy.py:16, evaluate.py:48, monitor.py:64 | `FakeMlflowClient` — **returns `[]` where real raises** | divergence → G-230 |
| optuna (`create_study`, 25 trials) | tuning.py:110-124 | real (closed-form ridge is cheap) | ✓ |
| parquet/fs read/write | all data/feature/pipeline modules | real `tmp_path` | ✓ |
| `datetime.now()` | monitor.py:110 | not faked (report timestamp) | acceptable |
| `np.random.seed` | monitor.py:70 | dead call — no np.random consumer | → G-226 |
| `sys.path`/`sys.modules` | feast_materialization.py:17-23 | mutated, never restored | → G-229 |
| env vars / subprocess / threads | none | — | single-process CLI |

## Dimension findings

| Dim | Suspect / measured | Evidence | Disposition |
|---|---|---|---|
| D1 | **`build_from_trips` `shift(-1)` labels the next OBSERVED row, not the next hour** — across a gap the target is a later hour's count | probe: loc hours {0:2 trips, 2:1} (hour 1 missing) → row hour-0 gets `next_hour_pickup_count=1` = hour-2's value; groupby produces no zero-rows so gaps are pervasive in real taxi data | **G-212 S1** |
| D1/D4 | **evaluate writes `evaluated=true`+mae/rmse tags before `require_within`; deploy promotes `latest_versions[0]` ignoring tags** | FakeMlflowClient probe: `max_mae=0.001` → run raised `Invalid MAE 18.5` yet `tag_calls` already carried evaluated/mae/rmse on v7; deploy.py has no tag check — the quality gate cannot block promotion | **G-213 S1** |
| D1/D4 | **`tracking_uri: sqlite:///projects/nyc_taxi_demand_forecasting/mlflow.db` is cwd-relative** | physical evidence: three divergent stores on disk — project-root `mlflow.db` (cwd=repo root), `projects/nyc_taxi_demand_forecasting/mlflow.db` nested inside the project (cwd=project dir), `notebooks/projects/.../mlflow.db` (cwd=notebooks); +`mlruns/` stray. Train/deploy/api invoked from different cwds read/write different registries | **G-214 S1** |
| D1 | `_mapping` str-coerces nested keys | `{1:,'1':}` → `{'1':}` silently overwritten (G-199 class, second instance) | **G-215 S3** |
| D1/D3 | bools leak through `_integer`/`_float`/`_integer_list`; `months: []` accepted | `months:[on,off]`→`(True,False)`, `source_url(True)`→`...-01.parquet`; `test_size:on`→`1.0`; `months:[]`→`()` then `min()` raw ValueError at features.py:39 | **G-216 S3** |
| D1 | `config_path.parent.parent` anchors root | `load(/tmp/x/project.yaml)` → `paths.root=/tmp` | **G-217 S3** |
| D5 | `include:` stub configs unimplemented | `load(configs/train.yaml)` → `ValueError: Invalid project config key paths` — wrong key named; 4 stub files | **G-218 S3** (AX-1: 2nd pkg) |
| D1/D4 | api import-time init + silent swallow | real import 2.22 s: `parents[3]` config anchor + `FeatureStore(repo_path)` fs hit + global `set_tracking_uri` + `load_model`; sentinel `load_model` raise → `_model=None` zero log → unexplained 503 | **G-219 S3** |
| D1 | `features["pickup_count"]` outside fetch guard | TestClient probe: df lacking the column → raw `500 Internal Server Error` (KeyError), not the 404 contract | **G-220 S3** |
| D8 | `detail=f"...{exc}"` echoes internals | probe: fetch `RuntimeError("sqlite:///internal/secret.db…")` → 500 body contains it verbatim | **G-221 S3** |
| D1/D5 | `cli.main()` no catch | `collect --config missing.yaml` → `pipeline_command_failed` JSON then raw `FileNotFoundError` traceback | **G-222 S3** |
| D1 | `DemandDatasetSplitter.split` unbounded | `test_size` 0→10/0, 1.0→1/9, 1.5→1/9, −0.1→10/0; n=10 ts=0.25→holdout 30% (`int` truncation); n=1→empty holdout→`calculate` ValueError mid-tune (G-205 class) | **G-223 S3** |
| D1 | monitor `except Exception` masks any champion failure → silent fallback to latest; report hardcodes `Alias: @champion` anyway | probe: `load_model` `RuntimeError("corrupt artifact")` → served version 9 not champion 2; report line :130 prints literal `@champion` regardless | **G-224 S3** |
| D1 | monitor report prints uncomputed drift | 4 rows emit literal `+0.00%`/`Normal` (:160-173) — means computed, drift never is; `train_mean==0` guard reports `0.0%`/`Normal` on unbounded relative drift (test pins it) | **G-225 S3** |
| D7 | `np.random.seed(random_state)` at :70 | no `np.random` consumer exists — dead call mutating global RNG | **G-226 S3** |
| D1/D8 | collector `.exists()`-only freshness + non-atomic `write_bytes` | probe: planted HTML `yellow_tripdata_2023-01.parquet` → collect skips (0 requests) → downstream `read_parquet` `ArrowInvalid`; a crashed write poisons the cache permanently | **G-227 S3** |
| D1 | `preprocess` concatenates every `*.parquet` in raw/, ignoring `collection.months`; `features` materializes only the config-month window | probe: months=[1] + stray Feb file → interim carries month-2 rows; feast `materialize(…Apr 1)` then drops them from the online store silently | **G-228 S3** |
| D4/D7 | `LocalFeastMaterializer.apply` sys.path pollution + `sys.modules` staleness | probe: `apply(repoA)` then `apply(repoB)` → B receives A's `entity-A`/`view-A` objects; both sys.path entries persist | **G-229 S3** |
| D1/D9 | `get_latest_versions` deprecated (mlflow warns since 2.9) and its `if not …` guards are dead for missing models | real probe: missing name → `MlflowException` (friendly `ValueError` unreachable at evaluate.py:52/deploy.py:20/monitor.py:31); registered-empty → `[]` + DeprecationWarning. `FakeMlflowClient` returns `[]` where real raises — fake contract diverges, pinning unreachable arms | **G-230 S3** |
| D4 | dead surface: `MedianDemandRegressor`, `LinearDemandRegressor`, `MlflowDemandModelRegistry`; registry getter `registered_model_name()` side-effects `set_tracking_uri` | grep: 0 production consumers (tests only); `DemandRegressor` protocol earns its place via `PyfuncDemandModel` param | **G-231 S3** |
| D4/D5 | duplication: `_feature_columns` 5-tuple ×6 sites; entity-df prep block verbatim ×3 | training.py:151-157, tuning.py:36-42, api.py:80-86, batch_predict.py:11-17, monitor.py:78-84, +eval :60-66; prep: training.py:171-182 ≈ tuning.py:64-79 ≈ evaluate.py:19-25 | **G-232 S3** |
| D5 | feast import seam inconsistent ×3 styles | `from feast import` top-level (features.py:5) vs in-run (evaluate.py:27) vs `import_module` (tuning/feast_materialization/batch_predict) — different fake mechanics per module | **G-233 S3** |
| D3 | type-honesty: `cast(pd.Series, model.predict())` monitor.py:87 (runtime ndarray — harmless downstream, dishonest annotation); bare `# type: ignore` training.py:124 + `name-defined` :118; `cast(pd.DataFrame,…)` tuning.py:86-98 | reading + AF-92/93 contract (pyfunc→ndarray); casts carry no invariant comment | **G-234 S3** |
| D9/D10 | test depth: mutation battery 4/8 survived; fake-contract divergences; 1 bdd scenario; privates-patching | battery: killed shift-dir/split/skip-exists/api-empty; survived `duration >0`→`>=0`, drift `>10`→`>=10`, int-bool exclusion, int-acceptance in `_float`. `FakePyfuncModel.predict` returns `pd.Series` — monitor/evaluate/batch paths still hide the ndarray contract AF-93 fixed only at api. bdd: 1 happy scenario; `patch`/`MagicMock` on `_model`/`fetch_online_features` (ADR-0005). AX-2 surfaces: 8 CLI cmds, `/predict` 404/503/500, batch predict, feast apply+materialize, monitor report | **G-235 S4** |
| D2 | `pd.concat` all-months + `response.content` full-buffer | bounded ~100 MB/month, once per CLI run | suspect, no row |
| D2/D6 | no unbounded loops; tracemalloc n/a — no long-lived stores | surface scan | clean |
| D7 | `set_tracking_uri` global mutation ×5 sites (api:23, registry:14, train:13, training:224, monitor:63, evaluate:47) | single-process CLI; per-process consistent — folded into G-214 fix | noted |
| D1 | `_resolve_best_alpha` silent `1.0` ×3 fallbacks; `float(best_alpha_str)` raw error | fallbacks are test-pinned (deliberate); tampered-param path lands in cli-traceback class | suspect, no row |
| D8 | `source_url`/`tracking_uri` untrusted-input surface | config is repo-committed (author trust boundary); parquet via pyarrow, yaml via audited `YamlMappingLoader` | clean |
| D4 | `evaluation/metrics.py` re-export shim | real consumer training.py:17 (AU-17 twin adjudicated keep) | clean |
| D1 | `batch_predict` missing cols → `KeyError` naming columns; `preprocessing` missing col → `ArrowInvalid` schema dump | errors name the column; lack file context | suspect, no row |

## Measurements

- `_mapping` collision: `{1:"int-val","1":"str-val"}` → `{'1':'str-val'}`.
- Bool leak: `months:[on,off]`→`(True,False)`; `source_url(True)`→`yellow_2023-01.parquet`; `test_size:on`→`1.0`. `months:[]`→`()`→`min() arg is an empty sequence`.
- Anchor: `load(/tmp/<x>/project.yaml)` → `paths.root=/tmp`.
- `include:` → `ValueError: Invalid project config key paths: expected mapping`.
- Tracking-uri divergence: `mlflow.db` ×3 (project root, nested `projects/…/`, `notebooks/projects/…/`) + `mlruns/` — all gitignored, all physically present.
- `split(n=10)`: ts 0→10/0, 0.25→7/3, 1.0→1/9, 1.5→1/9, −0.1→10/0; empty→0/0.
- `shift(-1)` mislabel: hours {0,2} → hour-0 row labeled with hour-2 count.
- api probes (TestClient, faked feast/mlflow): sentinel `load_model` raise → `_model=None` silent; missing `pickup_count` → `500 Internal Server Error` plaintext; fetch RuntimeError → `detail` echoes `sqlite:///internal/secret.db…`; real import 2.22 s.
- cli: `collect --config missing.yaml` → JSON fail line + raw traceback.
- evaluate: threshold-fail run still wrote `evaluated=true`, `mae`, `rmse` tags; deploy promotes latest unconditionally.
- monitor: corrupt-champion `load_model` → served v9 while report claims `@champion`; literal `+0.00%` ×4; zero-baseline → `0.0%`/`Normal` (test pins).
- collect: corrupt `.parquet` skipped (0 requests) → `ArrowInvalid` downstream.
- preprocess: stray month-2 file → interim contains months {1,2} under `months=[1]`; materialize window is config-derived (test pins 2023-01-01→2023-04-01).
- feast apply: `apply(repoA); apply(repoB)` → B got A's objects; sys.path grew by 2.
- mlflow probe (real sqlite): missing model → `MlflowException`; registered-empty → `[]` + `DeprecationWarning (since 2.9.0)`.
- Mutation battery (live flip → pytest → revert): killed 4/8 (`shift(-1)`→`shift(1)`, `1-ts`→`ts`, `exists()`→`False`, `features.empty`→`False`); survived 4/8 (`>0`→`>=0` duration, `>10.0`→`>=10.0` drift boundary, bool-exclusion in `_integer`, `int|float`→`float` strictness).
- Coverage: `pytest --cov` own-tree 100% / 1483 stmts (floor 95); vulture clean; pyright strict 0 errors (pre-existing).

## Gaps promoted

| Gap ID | Severity | One-line |
|---|---|---|
| G-212 | S1 | `shift(-1)` labels next-observed-row not next-hour — mislabeled targets across every hour gap |
| G-213 | S1 | evaluate tags `evaluated=true` before the gate raises; deploy ignores tags — promotion ungated |
| G-214 | S1 | cwd-relative `tracking_uri` → three divergent mlflow.db stores on disk (registry split-brain) |
| G-215 | S3 | `_mapping` str-coerces nested keys (G-199 class) |
| G-216 | S3 | YAML bools accepted by numeric guards; `months: []` → raw `min()` crash |
| G-217 | S3 | `config_path.parent.parent` anchors to wrong root (G-201 class) |
| G-218 | S3 | `include:` stub configs unimplemented; error names wrong key (G-206 class, AX-1 2nd) |
| G-219 | S3 | api import-time init (2.22 s) + `except Exception`→`_model=None` silent swallow (G-196 class) |
| G-220 | S3 | `features["pickup_count"]` outside fetch guard → raw 500 (G-197 class) |
| G-221 | S3 | `detail={exc}` echoes internal error text to clients (G-198 class) |
| G-222 | S3 | `cli.main()` no catch → raw tracebacks (G-203 class) |
| G-223 | S3 | `split` accepts degenerate `test_size` + int-truncates holdout (G-205 class) |
| G-224 | S3 | monitor `except Exception` fallback serves latest silently; report prints `@champion` anyway |
| G-225 | S3 | monitor report hardcodes `+0.00%`/`Normal` on 4 features; zero-baseline → `0.0%` Normal |
| G-226 | S3 | dead `np.random.seed` mutates global RNG; no consumer |
| G-227 | S3 | collector `.exists()`-only check resurrects corrupt/truncated downloads; non-atomic write |
| G-228 | S3 | preprocess ingests all `*.parquet` ignoring `collection.months`; materialize window drops them |
| G-229 | S3 | `apply(repoB)` applies repoA objects (sys.modules staleness); sys.path grows permanently |
| G-230 | S3 | `get_latest_versions` deprecated; missing-model raises MlflowException — 3 friendly-error arms dead; fake diverges |
| G-231 | S3 | dead surface: `Median`/`Linear` regressors + `MlflowDemandModelRegistry` side-effecting getter |
| G-232 | S3 | `_feature_columns` literal ×6; entity-df prep ×3 verbatim |
| G-233 | S3 | feast import seam in 3 styles — inconsistent fake mechanics |
| G-234 | S3 | `cast(pd.Series, ndarray)` type lie + bare `# type: ignore`s |
| G-235 | S4 | 4/8 mutants survived; fake divergences (Series return, `[]` vs raise); 1 bdd scenario; privates-patching; AX-2 surfaces |

## Tail

- Sizing: 1570 LOC, one session — right as filed (M).
- This is the template's real body: where AU-17 found stubs, here lie real
  defects — the `shift(-1)` label corruption and the ungated promotion path
  are the milestone's most consequential findings so far (a trained-on
  mislabeled-targets model ships to a registry that promotion never gates).
- Template-shared classes now confirmed ≥2× for AX-1: `_mapping` coercion
  (G-199+G-215), YAML bools (G-200+G-216), `parent.parent` anchoring
  (G-201+G-217), `include:` stubs (G-206+G-218), cli-traceback (G-203+G-222),
  `split` bounds (G-205+G-223), ambient/cwd mlflow state (G-207+G-214),
  api echo/KeyError/eager-init (G-196/197/198+G-219/220/221).
- AF-93 already landed here (predict normalization) — api ndarray contract
  fixed at the serving seam; monitor/evaluate/batch fakes still Series-typed.
- AX-2 surfaces: 8 CLI subcommands, `/predict/{id}` error arms (unit-covered,
  bdd-absent), `BatchDemandPredictor`, `feast apply`+`materialize`, monitor
  report write.
- Next: AU-19 `projects/athena_emulator` parity glue (XS).
