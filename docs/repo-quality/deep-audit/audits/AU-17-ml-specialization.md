# AU-17 — ml_specialization audit (2026-10-05)

MA-6 third item. Target: `projects/ml_specialization` — **731 src LOC / 489
SLOC** (radon raw) across 23 modules; weight concentrated in
`configuration.py` (245), `inference/api.py` (98), `interfaces/cli.py` (74),
`inference/batch_predict.py` (34); the remaining 15 modules are 4–21 LOC each
(mostly template stub bodies). Test suite: **280 test LOC, 9 tests** (the
README inventory's "zero test LOC" is stale — tests arrived with the QG/QH
gate wiring). Gates run this session: `pytest` 9 passed; `pyright src` strict
0 errors assumed via `make quality` chain (`lint type-check test coverage
complexity dependencies security maintainability` — full sibling gate set,
`radon -e`/`xenon`/`bandit`/`vulture`/`semgrep`/`deptry`, floor 75).

This package is the **unfilled scaffold template**: the sibling
`nyc_taxi_demand_forecasting` (AU-18) is the same skeleton with real bodies —
same class names, same pipeline shape — so every stub here has a reference
implementation there. Dependency: `mlops-shared` only (AU-01 contract verdicts
reused — `YamlMappingLoader`, `RepositoryPathResolver`,
`MlopsLoggingConfigurator`, `PipelineCommandRegistry`,
`RegressionMetricCalculator` all already audited).

## Surface inventory

| Module | SLOC | Public symbols | Entry |
|---|---|---|---|
| `configuration.py` | 193 | `ProjectPaths`, `CollectionConfig.source_url`, `FeatureConfig`, `MlflowConfig`, `TrainingConfig`, `EvaluationConfig`, `FeastConfig`, `ProjectConfig`, `ProjectConfigLoader.load` + 8 private readers | consumed by cli/api/pipelines |
| `interfaces/cli.py` | 62 | `create_parser`, `create_registry`, `run_command`, `main` | ★ `python -m …interfaces.cli` (Makefile recipes ×8) |
| `pipelines/{collect,preprocess,features,train,tune,evaluate,deploy,monitor}.py` | 9 ea | `run(config_path)` ×8 | ★ CLI subcommands |
| `inference/api.py` | 71 | `app`, `fetch_online_features`, `predict_demand` | ★ `GET /predict/{location_id}` (uvicorn) |
| `inference/batch_predict.py` | 24 | `BatchDemandPredictor.predict` | none (zero callers) |
| `data/{collection,preprocessing,supervised_dataset}.py` | 12/9/8 | `TlcYellowTaxiParquetCollector`, `YellowTaxiTripPreprocessor`, `NextHourDemandDatasetBuilder` | none (zero callers) |
| `features/{hourly_demand,feast_materialization}.py` | 8/4 | `HourlyDemandFeatureBuilder`, `LocalFeastMaterializer` | none (zero callers) |
| `models/{training,tuning,registry}.py` | 5/4/6 | `DemandDatasetSplitter`, `DemandModelTuner`, `MlflowDemandModelRegistry` | none (zero callers) |
| `evaluation/metrics.py` | 5 | re-export `__all__` of mlops_shared | test-only import |
| `feature_repo/{data_sources,entities,feature_views}.py` | (outside src) | feast defs | `feast apply` CLI convention (cwd sys.path imports) |
| `__init__.py` ×8 | 0 | — | — |

## Callgraph

```
★ cli.main() [cli.py:66]
  ├─ MlopsLoggingConfigurator().configure()          mlops-shared (AU-01)
  ├─ create_registry() → PipelineCommandRegistry      [:33-45]
  ├─ create_parser(registry).parse_args()             [:21-30]
  └─ run_command(registry, cmd, Path(config))         [:48-63]
      ├─ logger.info started (JSON extras + uuid4 correlation_id) [:51-57]
      ├─ registry.runner_for(cmd)(config_path)        [:59]
      │   └─ pipelines.<cmd>.run(config_path)         [pipelines/*.py:7]
      │       ├─ ProjectConfigLoader().load(config_path)
      │       │   ├─ YamlMappingLoader.load           → FileNotFoundError /
      │       │   │     ValueError escape             [configuration.py:87]
      │       │   ├─ config_path.parent.parent root   [:88] (probe C)
      │       │   ├─ _paths/_collection/_features/_mlflow/_training/
      │       │   │   _evaluation/_feast              [:100-177]
      │       │   │   ├─ _mapping str() key coercion  [:201-205] (probe A)
      │       │   │   ├─ _integer/_float/_integer_list accept bool (probe B)
      │       │   │   └─ _absolute_tracking_uri       [:179-194] (probe D)
      │       │   └─ returns ProjectConfig
      │       └─ logger.info "<cmd>_pipeline_completed" — NO WORK DONE
      │           (never touches the domain class it names; zero calls)
      ├─ except Exception → logger.exception + raise  [:60-62]
      │   → main() catches nothing → raw traceback on stderr (probe E)
      └─ logger.info completed                        [:63]

★ import ml_specialization.inference.api            [api.py:14-28]
  ├─ _config_path = Path(__file__).parents[3]/configs/project.yaml [:17]
  ├─ _config = ProjectConfigLoader().load(_config_path)            [:18]
  │     └─ config missing/invalid → module unimportable (collection-time)
  ├─ _store = FeatureStore(repo_path=…)                            [:19]
  ├─ mlflow.set_tracking_uri(…)  — mutates process-global          [:22]
  └─ _model = mlflow.pyfunc.load_model(models:/name@champion)      [:25-28]
        └─ except Exception → _model = None (sentinel probe: swallowed,
          zero log — cause unrecoverable)

★ GET /predict/{location_id} → predict_demand       [api.py:52-98]
  ├─ _model is None → HTTPException 503             [:59-63]
  ├─ fetch_online_features(location_id)             [:66 → :31-49]
  │   └─ _store.get_online_features(…).to_df()      [:45-48] (never tested
  │       unmocked — coverage 37-49 uncovered)
  │   └─ except Exception → 500 + detail=str(exc)   [:67-71] (probe: internals echoed)
  ├─ features.empty or isna(features["pickup_count"].iloc[0]) → 404 [:73-77]
  │   └─ df lacking pickup_count col → KeyError → raw 500 (probe)
  ├─ features[feature_cols] → _model.predict        [:86-90]
  │   └─ cast(pd.Series, predict()) — ndarray model → .iloc AttributeError
  │       → raw 500 (probe; sklearn pyfunc returns ndarray)
  └─ return dict (features.to_dict records[0])      [:94-98]

BatchDemandPredictor.predict                        [batch_predict.py:22-34]
  └─ import_module("mlflow") → load_model → read_parquet →
     loc[:, _feature_columns] (missing col → raw KeyError) → assign →
     to_parquet. Zero callers (grep).

Domain classes (all zero-call-site — own docstring examples only):
  TlcYellowTaxiParquetCollector.collect → returns paths never written (probe F1)
  YellowTaxiTripPreprocessor.preprocess → writes (0,0) empty parquet (probe F2)
  NextHourDemandDatasetBuilder.build → verbatim copy (probe F3)
  HourlyDemandFeatureBuilder.build → verbatim copy (probe F3)
  LocalFeastMaterializer.apply → mkdir only, no feast apply (probe F4)
  DemandDatasetSplitter.split → real logic, unbounded test_size (probe G)
  DemandModelTuner.tune → returns 1.0 unconditionally (probe F5)
  MlflowDemandModelRegistry.promote_champion → ambient MlflowClient() →
      silently wrote mlflow.db to probe cwd (probe K)

feast apply (external CLI) → feature_repo/*.py
  └─ `from data_sources import` — feast cwd/sys.path convention
```

## Boundary table

| Boundary | Where | Faked as | Test |
|---|---|---|---|
| config YAML (`read_text` + `yaml.safe_load` via `YamlMappingLoader`) | configuration.py:87 | real `tmp_path` files | test_configuration.py |
| `config_path` relative root anchor (`parent.parent`) | configuration.py:88 | — | none |
| parquet IO (`pd.read_parquet`/`to_parquet`) | data/*, features/hourly_demand, batch_predict | — | none (0% modules) |
| mlflow tracking URI + model load | api.py:22-26 (import-time), batch_predict.py:25-26, registry.py:12 (ambient client) | `patch("…_model")` MagicMock on the private | test_api/test_predict |
| Feast `FeatureStore` + `get_online_features` | api.py:19,45-48 | `patch("…fetch_online_features")` MagicMock | test_api/test_predict |
| env/cwd writes | mlflow default `sqlite:///mlflow.db` in cwd (registry probe), `set_tracking_uri` global | — | none |
| `feast` CLI (sys.path convention) | feature_repo/*.py | — | none |
| process logging (`MlopsLoggingConfigurator`) | cli.py:67 | — | none |
| no subprocess, no RNG (random_state is a config int), no threads | — | — | — |

## Dimension findings

| Dim | Suspect / measured | Evidence | Disposition |
|---|---|---|---|
| D1/D3 | **`cast(pd.Series, _model.predict(…))` then `.iloc[0]`** (api.py:88-92) — mlflow pyfunc returns whatever the flavor returns; the dominant sklearn flavor yields `np.ndarray` → `.iloc` `AttributeError` → raw 500 on every request. Probe: `_model` returning `np.array([12.5])` → `500 Internal Server Error`. The `cast` carries no invariant comment and the test mock pins `pd.Series`, hiding the real contract | TestClient probe | **G-195 S1** |
| D1/D4 | **module-level eager init + blanket swallow** (api.py:17-28): `parents[3]`-anchored config load, `FeatureStore` construction, `mlflow.set_tracking_uri` global mutation, and `load_model` all run at import; `except Exception: _model = None` — sentinel `RuntimeError("SENTINEL_BREAKAGE")` probe → `_model=None` with zero log/record, cause unrecoverable until a 503. Measured import cost 8.14 s (paid at pytest collection). Failure asymmetry: model-load errors → silent `None`; config errors → module unimportable | reload probe + timeit | **G-196 S3** |
| D1 | **`features["pickup_count"]` outside the fetch guard** (api.py:73) — df missing the column → `KeyError` → raw 500 (probe), bypassing the 404 contract | TestClient probe | **G-197 S3** |
| D8 | **`detail=f"…{exc}"` echoes internals** (api.py:70) — probe: `RuntimeError("sqlite:///secret/path.db internal detail")` reflected verbatim in the 500 body | TestClient probe | **G-198 S3** |
| D1 | **`_mapping` `str()`-coerces nested keys** (configuration.py:201-205) — probe: `collection: {1: a, '1': b}` → `{'1': 'b'}` silent overwrite; `on:` key → `'True'`. G-16 class — AF-10 fixed the *template*; this live project still carries the pre-fix body (template fixes don't retro-apply) | yaml probe | **G-199 S3** |
| D1/D3 | **YAML bools pass the numeric guards** — `isinstance(True, int)` is `True`: `months: [on, off]` → `(True, False)` accepted and `source_url(True)` renders month `01`; `test_size: on` → `1.0` (100% holdout). configuration.py:218-245 | yaml probes | **G-200 S3** |
| D1 | **`config_path.parent.parent` silent root anchor** (configuration.py:88) — config outside `<root>/configs/` resolves `paths.*` against the wrong root: probe `/tmp/x.yaml` → `raw_data=/tmp/data/raw`. No check that the config sits under a configs dir | probe | **G-201 S3** |
| D1 | **`sqlite:///:memory:` corrupted** (configuration.py:185-194) — `:memory:` is relative → `sqlite://///proj/:memory:` (a file literally named `:memory:`); the valid sqlite in-memory URI silently becomes a file | transform probe | **G-202 S3** |
| D1/D5 | **CLI error paths exit via raw traceback** — probe `collect --config missing.yaml`: JSON `pipeline_command_started`/`failed` lines log correctly, then `FileNotFoundError` traceback to stderr, rc=1. `main()` (cli.py:66-70) has no catch; `run_command` re-raises (:60-62). G-17/G-40/G-178 class | CLI probe | **G-203 S3** |
| D1/D4 | **pipeline `run()`s log "completed" having done zero work; all 9 domain classes unwired + fabricate artifacts**: grep — every class's only reference is its own docstring example (nyc_taxi wires the same names to real bodies). Probes: `collect()` returns `yellow_tripdata_2023-0{1,2}.parquet` paths that don't exist (and never calls `source_url` — dead config surface); `preprocess` writes a `(0,0)` empty parquet as "cleaned trips"; `supervised_dataset`/`hourly_demand` copy input to output verbatim (`in==out: True`); `feast_materialization.apply` only `mkdir`s (no `feast apply`, empty dir); `tune` returns `1.0` unconditionally. A caller of any of these gets a success-shaped result with nothing behind it — worse than a `NotImplementedError` stub | call probes + grep | **G-204 S3** |
| D1 | **`DemandDatasetSplitter.split` unbounded** (training.py:14-17): probes — `test_size` 0→train=100/test=0; 1.0→1/99; 1.5→1/99; −0.1→100/0 — no rejection; `n=10, ts=0.25` → holdout 30% (int() truncation); empty df → 0/0 silently. The one piece of real logic in the package | parametrized probe | **G-205 S3** |
| D5 | **`configs/{train,evaluate,predict,materialize}.yaml` are `include: project.yaml` stubs — `include` is unimplemented**: probe `load(configs/train.yaml)` → `ValueError: Invalid project config key paths: expected mapping` — names the wrong thing. Same stub files exist in nyc_taxi (template-shared; AX-1 pattern candidate) | load probe | **G-206 S3** |
| D4/D7 | **`MlflowDemandModelRegistry` rides the ambient tracking URI** (registry.py:11-12): `MlflowClient()` with no `set_tracking_uri` silently created `mlflow.db` (712 KB) in the probe cwd before failing `Registered Model … not found`. Hidden process-global dependency — the only place that sets it is api.py:22 | tmp-cwd probe | **G-207 S3** |
| D9 | **coverage report is polluted + blind**: bare `--cov` TOTAL 84% (445 stmts) includes 5 mlops_shared files (106 stmts) and **omits unimported modules entirely** — data/features/models/batch_predict never imported → invisible. Scoped `--cov=src` → **64%**; the AF-46 convention `source=["src","tests"]` → **73% < the declared 75 floor**. The gate is green today only because pollution and import-blindness inflate the number | 3 coverage runs | **G-208 S4** |
| D9/D10 | **test depth**: 9 tests/280 LOC. Mutation battery (live flip → revert): M1 `_mapping` `isinstance(dict)`→`True` SURVIVED, M2 `_string` str→(str,int) SURVIVED, M5 `run_command` drop-`raise` (swallow after logging) SURVIVED; killed: M3 503→500, M4 `or`→`and` 404-check. Uncovered: configuration reject arms :207,214,223,232,243; `_absolute_tracking_uri` non-sqlite/abs arms :187,191; `fetch_online_features` body :37-49 (always mocked — the Feast call itself never runs); api fetch-failure arm :67-68; cli `run_command`/`main` :51-74; all 8 pipeline bodies :13-14; 9 modules at 0%. `test_pipeline_command_registry_reports_invalid_command` asserts `"train" in names()` — name/body mismatch. bdd: 1 happy-path scenario; `MagicMock`/`patch` on privates `_model`/`fetch_online_features` instead of named fakes (ADR-0005); `predict.assert_called_once()` asserts no args. Surfaces for AX-2: 8 CLI commands, `/predict` error arms, batch predict, `feast apply` | battery + coverage lines | **G-209 S4** |
| D4 | `evaluation/metrics.py` is a pure re-export shim (2 stmts + `__all__`) — but nyc_taxi's identical shim has real consumers (`models/training.py:17`), so the seam is the template's intended alias, awaiting implementation | sibling comparison | suspect, no row |
| D8 | `source_url_template.format(year=…)` — int/str field interpolation, author-committed config (G-04/G-34 trust boundary); `feature_repo` bare imports are the `feast apply` cwd convention | reading | suspect, no row |
| D2 | no unbounded loops; `split` `.copy()` ×2 is bounded by input | reading | clean |
| D6 | no stores/caches/history; `_model`/`_store` module singletons are load-once | construction | clean |
| D7 | `_store`/`_model` shared across uvicorn requests — read-only post-import; single-process-by-design (`set_tracking_uri` global noted in G-196/G-207) | construction | noted, no row |
| D3 | `dict[str, Any]` return on `predict_demand` (:53) — JSON response boundary shape, honest | reading | clean |

## Measurements

- **Coverage** (this session): bare `--cov` TOTAL 84% (includes
  `mlops_shared/{config,evaluation,logging,paths,pipeline}.py` = 106 stmts —
  pollution confirmed, AF-07 residual verbatim); `--cov=src` → 64%;
  `--cov=src --cov=tests` (AF-46 convention) → **73% vs floor 75**.
  Zero-stmt modules: data/collection(6), preprocessing(9),
  supervised_dataset(8), feast_materialization(4), hourly_demand(8),
  batch_predict(14), registry(6), training(5), tuning(4) — 64 stmts = 21% of
  the package invisible to the bare-`--cov` gate.
- **Import cost**: `import ml_specialization.inference.api` → 8.14 s cold
  (mlflow+feast+config+load_model attempt); `_model=None` on this checkout
  (no champion registered — swallow invisible without a probe).
- **Probes** (all in tmp dirs / in-process, source untouched):
  `collection: {1: a, '1': b}` → `{'1': 'b'}`; `months: [on, off]` →
  `(True, False)`; `test_size: on` → `1.0`; `/tmp/x.yaml` → root `/tmp`;
  `sqlite:///:memory:` → `sqlite://///proj/:memory:`;
  `configs/train.yaml` → `ValueError … key paths`;
  `collect()` → 2 paths, both `exists()==False`; `preprocess` → parquet
  `(0,0)`; verbatim copies `equals()` → `True`; `feast apply` → empty dir;
  `tune` → `1.0`; `split` degenerate rows as tabled above;
  `promote_champion` in `/tmp/au17reg` → created `mlflow.db` 712 KB;
  CLI `collect --config missing.yaml` → rc=1 + traceback.
- **TestClient probes** (`raise_server_exceptions=False`): ndarray predict →
  `500 Internal Server Error`; df missing `pickup_count` → `500`;
  fetch RuntimeError → `500 {"detail":"…sqlite:///secret/path.db internal
  detail"}`.
- **Mutation battery** (live flip → targeted pytest → revert; `git status`
  verified clean): 3/5 survived — M1 dict-guard→`True`, M2 str-guard widened,
  M5 drop `raise`; killed M3 (503→500), M4 (`or`→`and`).

## Gaps promoted

| Gap ID | Severity | One-line |
|---|---|---|
| G-195 | S1 | `cast(pd.Series, _model.predict())` → `.iloc` — ndarray-returning pyfunc (standard sklearn flavor) → raw 500 on every predict |
| G-196 | S3 | api.py module-level eager init (parents[3] config anchor, FeatureStore, global `set_tracking_uri`, `load_model`) + `except Exception` → `_model=None` swallows the cause silently |
| G-197 | S3 | `features["pickup_count"]` KeyError outside the fetch guard → raw 500 |
| G-198 | S3 | `detail=str(exc)` reflects internal exception text in the 500 body |
| G-199 | S3 | `_mapping` `str()`-coerces nested keys — `{1:,'1':}` silent collision (G-16 class; AF-10 fixed the template, not this live project) |
| G-200 | S3 | `_integer`/`_float`/`_integer_list` accept YAML bools (`months: [on]`, `test_size: on` → True/1.0) |
| G-201 | S3 | `config_path.parent.parent` silently anchors paths to the wrong root when config isn't under `<root>/configs/` |
| G-202 | S3 | `sqlite:///:memory:` tracking URI corrupted to a `<root>/:memory:` file |
| G-203 | S3 | `main()` has no catch — config errors exit as raw tracebacks (G-17/G-40/G-178 class) |
| G-204 | S3 | 8 pipeline `run()`s log "completed" without work; 9 domain classes unwired and fabricate success artifacts (nonexistent paths, empty/verbatim parquet, `tune`→1.0, mkdir-as-apply) |
| G-205 | S3 | `DemandDatasetSplitter.split` — no `test_size` bounds (0/1/1.5/−0.1 accepted silently), int-truncation drifts holdout ratio, empty input → 0/0 |
| G-206 | S3 | `configs/*.yaml` `include:` stubs unimplemented → `ValueError` naming the wrong key; dead config files (template-shared → AX-1) |
| G-207 | S3 | `MlflowDemandModelRegistry` uses ambient `MlflowClient()` — writes `mlflow.db` to cwd when the caller didn't `set_tracking_uri` |
| G-208 | S4 | bare `--cov` reports 84% via pollution + import-blindness; scoped own-tree+tests is 73% — below the declared 75 floor |
| G-209 | S4 | test depth: 3/5 mutants survived; all reject/error arms uncovered; 1 happy-path bdd scenario; MagicMock privates-patching vs named fakes; AX-2 surface tags |

## Tail

- Sizing: 489 SLOC, one session — right as filed.
- This is the template's *empty* form: the `include:` stubs, the `metrics.py`
  re-export, and the unwired domain classes all have real counterparts in
  nyc_taxi (AU-18) — AU-18 can reuse the provenance verdicts here; the
  `include:` non-implementation and `_mapping` coercion are template-shared
  (AX-1 candidates, flagged ≥2× once AU-18 confirms).
- Template-drift pattern: AF-07/AF-10 fixed the scaffold template's gates and
  `_mapping`, but generated projects don't inherit fixes — G-199/G-208 are
  both "live project carries pre-fix shape" instances.
- AX-2 tags: 8 CLI subcommands, `/predict/{location_id}` success+error arms,
  `BatchDemandPredictor`, `feast apply` on `feature_repo/`.
