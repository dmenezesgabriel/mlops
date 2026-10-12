# AU-16 — sagemaker_* projects audit (2026-10-05)

MA-6 second item. Target: the four `projects/sagemaker_*` example packages —
`sagemaker_scikit_learn` (canonical, audited in full) + `sagemaker_catboost`,
`sagemaker_lightgbm`, `sagemaker_xgboost` (diff-swept). **170 src SLOC total**
(radon raw: 48/43/42/37) — one `train.py` + empty `__init__.py` + `py.typed`
per package. Non-src surface per package: `Dockerfile`/`Dockerfile.inference`
(build context `libs/sagemaker-local/docker` — assets audited in AU-15),
`configs/local.yaml` (reference doc, zero readers verified by grep), 3
notebooks (`training`/`batch_transform`/`pipeline`), `.gitignore` (`data/`),
`Makefile` with the full gate chain, `pyproject.toml`.

Test suite: 14 tests each (10 unit + 4 integration notebook runs), AAA-shaped.
Gates baseline per package (run this session): `pytest -m "not integration"`
10 passed/4 deselected ×4; `--cov` TOTAL 85/86/87/86% — **own-tree only, no
editable-dep pollution** (bare `--cov` measures cwd-rooted files; TOTAL lists
only `src/` + `tests/` — floors are at the measured values exactly);
`pyright src` strict 0 errors ×4; ruff/radon/xenon/deptry/bandit/vulture/
semgrep wired identically and green in `make quality`.

Dependency note: the only workspace dep is `sagemaker-local` (AU-15 contract
verdicts reused — `config_from_env`, `make_local_*_session`,
`cleanup_stale_serving_containers`, `docker/serve_app.py` are all its
already-audited surfaces). sklearn/joblib are workspace-real for scikit only;
the three boosting frameworks exist solely inside the built images (DEP001
ignores) — their wiring is tested through `sys.modules` named fakes.

## Surface inventory

| Module | SLOC | Public symbols | Entry |
|---|---|---|---|
| `train.py` (scikit) | 48 | `MODEL_DIR` :35, `_DATASETS` :38, `build_model` :53, `main` :66 | ★ `train` console script execs module; `main()` |
| `train.py` (catboost) | 43 | `MODEL_DIR` :32, `CATBOOST_TRAIN_DIR` :35, `_DATASETS` :37, `build_model` :50, `main` :62 | ★ same |
| `train.py` (lightgbm) | 42 | `MODEL_DIR` :31, `_DATASETS` :33, `build_model` :49, `main` :58 | ★ same |
| `train.py` (xgboost) | 37 | `MODEL_DIR` :34, `_DATASETS` :36, `build_model` :49, `main` :57 | ★ same |

Per-variant deltas are confined to: framework import + model classes, the two
`_DATASETS` entries, the default dataset, docstring example, catboost's
`tempfile`/`CATBOOST_TRAIN_DIR` (:33-35), `build_model` losing its return
annotation (see D3), Dockerfile framework pin (`catboost==1.2.7`,
`lightgbm==4.6.0` + `scikit-learn==1.6.1` for the sklearn wrapper dep,
`xgboost==2.1.4`; all add `libgomp1`). `test_notebooks.py` is byte-identical
across the four; `test_project_wiring.py` differs only in
`INFERENCE_FRAMEWORK_LINE`/`IMAGE_TAG`.

## Callgraph

Canonical (scikit); variants identical except the noted lines.

```
train console script → module exec → main() [train.py:66] ★
  ├─ os.environ.get("SM_HPS", "{}") → json.loads          [:67]
  │     └─ malformed JSON → raw JSONDecodeError (probe P1)
  ├─ hps.get("dataset", "california_housing")             [:68]
  │     └─ non-dict SM_HPS → AttributeError (probe P2)
  ├─ dataset not in _DATASETS → ValueError names value+set [:69-73]
  │     └─ unhashable dataset → TypeError (probe P3)
  ├─ _DATASETS[dataset] → (task, loader)                  [:74]
  ├─ loader() → sklearn load_*/fetch_*                    [:75]
  │     └─ california_housing lambda calls fetch TWICE    [:41-44] (probe P4)
  ├─ build_model(task).fit(x, y)                          [:76]
  │   ├─ "regression"     → Pipeline[StandardScaler,Ridge]   [:54-55]
  │   ├─ "classification" → Pipeline[StandardScaler,LogReg]  [:56-62]
  │   └─ else → ValueError — unreachable via main()
  │       (task is _DATASETS-constrained); reachable + tested
  │       as public API (test_build_model_rejects_unknown_task)
  ├─ os.makedirs(MODEL_DIR, exist_ok=True)                [:77]
  └─ joblib.dump(model, MODEL_DIR/model.joblib)           [:78]
        └─ serve side: model_fn=joblib.load in
          libs/sagemaker-local/docker/serve_app.py (AU-15)
```

Variant deltas: catboost `:50`/lightgbm `:49`/xgboost `:49` `build_model`
returns `CatBoost*|LGBM*|XGB*` `(Regressor|Classifier)` instead of Pipeline;
catboost passes `train_dir=CATBOOST_TRAIN_DIR` (keeps `catboost_info/` out of
the job's cwd — verified real on catboost 1.2.10); xgboost passes
`objective="multi:softprob"`; lightgbm `objective="multiclass"`.

## Boundary table

| Boundary | Where | Faked as | Test |
|---|---|---|---|
| env `SM_HPS` (JSON dict contract from the SDK) | train.py:67 (:63/:60/:58) | `monkeypatch.setenv` | `test_main_*` |
| env `SM_MODEL_DIR` (module-level snapshot :35/:32/:31/:34) | makedirs+dump :77-78 | `monkeypatch.setattr(MODEL_DIR)` + `tmp_path` | `test_main_*` |
| sklearn dataset loaders — `fetch_california_housing` hits figshare on cold cache (`~/scikit_learn_data`); `load_*` are bundled | `_DATASETS` lambdas | `_fake_california_housing` Bunch (fetch only) | `test_main_defaults` |
| image-only framework imports (catboost/lightgbm/xgboost absent from workspace) | module top imports | session `sys.modules` fake module + `Fake*` named fake classes (ADR-0005) | `test_train.py` ×3 |
| docker assets `serve`/`serve_app.py` | Dockerfile `COPY` (context = `libs/sagemaker-local/docker`) | content-pinned strings | `test_project_wiring.py` |
| docker/moto/jupyter-kernel stack | `test-notebooks` recipe (`/opt/mlops-venv` interpreter) | none — real stack, `integration` marker | `test_notebooks.py` |
| `configs/local.yaml` | — | — | none (reference doc; `config_from_env` consumes the env it describes) |

## Dimension findings

| Dim | Suspect / measured | Evidence | Disposition |
|---|---|---|---|
| D1/D8 | **`SM_HPS` trust boundary takes raw builtin exceptions** — `json.loads(os.environ.get("SM_HPS","{}"))` + `hps.get` (scikit :67-68; catboost :63-64; lightgbm :60-61; xgboost :58-59). Probes (scikit, real module): `SM_HPS='not-json'`/`''` → `json.JSONDecodeError` traceback; `'[1,2]'` → `AttributeError: 'list' object has no attribute 'get'` (:68); `'{"dataset": ["x"]}'` → `TypeError: unhashable type: 'list'` (:69). Well-formed odd values ARE clean: `{"dataset": 42}`/`null` → `ValueError: unsupported dataset: …; expected one of […]`. A hand-invoked `train` or a drifting SDK produces an unhelpful traceback mid-job instead of a named contract error (G-17/G-178 class) | env probes ×6 | **G-191 S3** |
| D2 | **`fetch_california_housing()` called twice per run** — the lambda reads `.data`/`.target` off two separate fetches (scikit :41-44). timeit on the cached pkz (`~/scikit_learn_data` warm): double 22.37 ms vs single 10.98 ms/call (n=20) — ~11 ms wasted re-parse per training run; cold path adds a second archive read. Bounded, once per job — a duplication slip, not a perf risk | timeit | **G-192 S3** |
| D3 | **`build_model` drops its return annotation in the 3 boosting variants** — scikit `-> Pipeline` (:53); catboost :50, lightgbm :49, xgboost :49 declare bare `def build_model(task: str):`. Measured: `uv run pyright src` strict → 0 errors on all four — `reportMissingReturnType=true` does not fire because pyright infers the return (Unknown for the stubless frameworks); control probe (`/tmp/au16-probe`, strict+`reportMissingReturnType`) confirms the rule only fires when inference fails. So the gate accepts the asymmetry: callers (`model.fit`) see `Unknown` where scikit sees `Pipeline` — declared intent lost, no type lie | pyright run + control probe | **G-193 S3** |
| D9 | **Assertion depth on construction kwargs + default dataset** — mutation battery (live flip → `pytest tests/test_train.py` → revert). scikit 6 mutants: 3 killed (`not in`→`in`, `exist_ok`→False, `get`→`[]`), 3 survived — `sorted(_DATASETS)`→`_DATASETS` (message still matches "unsupported dataset"; ordering-only, equivalent), `max_iter=1000`→999 (value unasserted — siblings assert `iterations`/`n_estimators`, asymmetric), **default `"california_housing"`→`"breast_cancer"` survived**: `test_main_defaults` only asserts `model.joblib` exists — the flipped default trains on real bundled breast_cancer and still lands the file (the `_fake_california_housing` monkeypatch isn't even called). Variants: `iterations`/`n_estimators` flips killed; `train_dir` drop, `verbose`, `objective` drops survive — but `train_dir`/`objective` carry real semantics (measured below), not just cosmetics | battery | **G-194 S4** |
| D1 | `objective` kwargs verified **redundant under the pinned frameworks**: xgboost 2.1.4 `XGBClassifier` on 3-class wine — `multi:softprob` fits without `num_class` (auto-inferred) and `predict` output is identical with/without the kwarg; lightgbm 4.6.0 `objective="multiclass"` drop → identical preds. Honest defensive pins, not defects | real-framework probes | suspect, no row |
| D1 | `train_dir` mutant is **behavioral**: real catboost 1.2.10 `CatBoostClassifier(iterations=5)` without `train_dir` writes `catboost_info/` into cwd — the kwarg keeps the mounted `/opt/ml/code` clean. Kwarg earns its place; gap is only that no test asserts it | real-framework probe | folded into G-194 |
| D3 | file-level pyright disables (`reportMissingTypeStubs`/`reportUnknown*` ×4 lines :16-19) — justified by the in-image dependency reality (comment :20-22); project-level `reportAttributeAccessIssue=false` has its own justification comment (Bunch attribute access) | pyproject + reading | clean |
| D4/D5 | `configs/local.yaml` has zero readers (grep) — self-described reference for the compose env contract (`SAGEMAKER_LOCAL_IMAGE_TAG` docker-compose.yml:114 → `config_from_env`); notebooks pass explicit `image_tag="sagemaker-<fw>:train"`. `_DATASETS` registry earns its place (dataset dispatch); `MODEL_DIR` import-time env snapshot is the training-image contract | grep + reading | clean |
| D6 | no state — module constants + one-shot process per job; nothing accumulates | construction | clean |
| D7 | single-threaded by construction: one `train` invocation per job container; `_DATASETS`/`MODEL_DIR` immutable post-import | construction | clean |
| D8 | Dockerfiles pin every pip dep (`==`), `--no-install-recommends`, COPY sources are the AU-15-audited `libs/sagemaker-local/docker` assets; `joblib.dump` writes a same-process artifact (load trust lives serve-side, AU-15). `SM_MODEL_DIR` path join is env-trusted inside the image — the SM_HPS row covers the env boundary | reading + pins | clean apart from G-191 |
| D10 | user-facing surfaces ↔ integration: `train` entry → `training.ipynb` (real container fit); artifact round-trip → `batch_transform.ipynb` (ftyp + row-count assertions via `x_test.csv.out`); pipeline wiring → `pipeline.ipynb` (`make_local_pipeline_session` + TrainingStep); all 4 `batch_transform.ipynb` also drive `cleanup_stale_serving_containers`. No `features/` dirs — bdd surface matrix defers to AX-2 per siblings | notebook cell map | surfaces tagged AX-2 |
| D9 | session-scoped `sys.modules` fakes never restore — suite-scoped by construction (fresh process per `pytest` run); `MODEL_DIR` monkeypatch reverts per-test | fixture reading | clean |
| D1 | `makedirs(MODEL_DIR)` on a path that is a file → `FileExistsError`; `SM_MODEL_DIR` is SDK-set in-image (env-trusted) | reading | suspect, no row |
| — | coverage floors sit at exact measured values (85/86/87/86 — QH-1 convention); any regression fails immediately — tight-by-design | Makefile vs run | noted, no row |

## Measurements

- **Coverage/pyright** (all four, this session): 10 passed + 4 deselected;
  train.py 96% each (residual = `if __name__ == "__main__"` line — :82/:77/
  :74/:72); TOTAL 85/86/87/86% own-tree only; pyright strict 0.
- **SM_HPS probes** (real `main()`, scikit): `'not-json'`/`''` →
  JSONDecodeError; `'[1,2]'` → AttributeError; `'{"dataset":["x"]}'` →
  TypeError unhashable; `{"dataset":42}`/`null` → clean named ValueError.
- **timeit** (cached `~/scikit_learn_data/cal_housing_py3.pkz`, n=20):
  double-fetch 22.37 ms vs single 10.98 ms/call.
- **Mutation battery**: scikit 3/6 killed — survivors M3 `sorted` (equivalent:
  message unordered but complete), M4 default-dataset flip (real: wrong
  dataset trains silently), M5 `max_iter` (value unasserted). catboost:
  `iterations` killed; `train_dir` drop survived (real cwd effect — catboost
  1.2.10 writes `catboost_info/`); `verbose` drop survived (cosmetic).
  lightgbm/xgboost: `n_estimators` killed; `objective` drops survived —
  measured equivalent under real pinned libs (identical predict output).
- **Real-framework probes** (uv ephemeral envs): xgboost 2.1.4 `multi:softprob`
  sans `num_class` → fits, preds identical to default objective;
  lightgbm 4.6.0 same; catboost 1.2.10 default `train_dir` → `catboost_info/`
  in cwd.

## Gaps promoted

| Gap ID | Severity | One-line |
|---|---|---|
| G-191 | S3 | `main()` parses `SM_HPS` with no shape check — malformed/non-dict/unhashable-dataset inputs escape as raw JSONDecodeError/AttributeError/TypeError tracebacks (all 4 `train.py`) |
| G-192 | S3 | scikit `california_housing` lambda fetches the dataset twice per run (+11.4 ms cached, double archive parse) |
| G-193 | S3 | `build_model` return annotation present in scikit (`-> Pipeline`), absent in catboost/lightgbm/xgboost — pyright accepts via inference, declared intent lost |
| G-194 | S4 | survived mutants: default-dataset flip (wrong dataset trains silently), `max_iter` unasserted, `train_dir`/`objective`/`verbose` kwarg drops unasserted in fake-module tests |

## Tail

- Sizing: 170 src SLOC across 4 packages is comfortably one session —
  batch shape correct as filed (no re-split needed).
- The 4-way diff confirms per-variant deltas are confined to framework
  selection; the defect classes above are shared except where noted.
- Reused verdicts: serve/runtime contract (`serve_app.py`, `serve`) is
  AU-15's; the offline-dataset-download concern is already G-190 (open,
  AF-91) — the batch_transform notebook's `fetch_california_housing` call is
  that row's surface, distinct from G-192's in-`train.py` duplicate call.
- AX-2 tags: `train` entry point + batch-transform surface (notebook-driven,
  no `features/`).
