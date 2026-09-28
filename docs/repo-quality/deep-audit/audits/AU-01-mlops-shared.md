# AU-01 — mlops-shared audit (2026-09-28)

Spike (MA-1): first rubric run end-to-end. Package: `libs/mlops-shared` —
276 src LOC (radon raw), 183 test LOC, 11 tests, all CC = A, coverage 93%
(stmts; `uv run pytest --cov`). No CLI/entry-points/`features/` — a leaf
library consumed by `nyc_taxi`, `ml_specialization`, and the
`data-science-scaffold` template.

## Surface inventory

| Module | LOC | Public symbols | Entry |
|---|---|---|---|
| `config.py` | 25 | `YamlMappingLoader.load` | config.py:14 |
| `datasets.py` | 27 | `DatasetLoader.load` (proto), `DatasetWriter.write` (proto) | datasets.py:15,25 |
| `evaluation.py` | 90 | `RegressionMetricThresholds` (proto), `RegressionMetrics.require_within`, `RegressionMetricCalculator.calculate` | evaluation.py:21,39 |
| `logging.py` | 50 | `JsonLogFormatter.format`, `MlopsLoggingConfigurator.configure` | logging.py:12,47 |
| `paths.py` | 23 | `RepositoryPathResolver.resolve`, `.root_path` | paths.py:14,22 |
| `pipeline.py` | 60 | `PipelineCommandRegistry.runner_for`/`.names`, `PipelineStep.run`/`.name`/`._run_step` | pipeline.py:19,28,42 |

Consumers (grep `mlops_shared` over src): `YamlMappingLoader`,
`RepositoryPathResolver`, `MlopsLoggingConfigurator`,
`PipelineCommandRegistry`, `RegressionMetricCalculator`,
`RegressionMetrics`/`RegressionMetricThresholds` — all used by
`nyc_taxi`+`ml_specialization` `configuration.py`/`cli.py`/`metrics.py`.
**`DatasetLoader`/`DatasetWriter`/`PipelineStep`: zero consumers or
implementers repo-wide** (videos has its own `pipeline_step.py` port;
scaffold template doesn't subclass `PipelineStep`).

## Callgraph

```
YamlMappingLoader.load ─ Path.read_text ─ yaml.safe_load ─ {str(k): v} ─ ValueError
RepositoryPathResolver.resolve ─ Path.is_absolute ─ (root/path).resolve
MlopsLoggingConfigurator.configure ─ StreamHandler ─ JsonLogFormatter ─ logging.basicConfig(force=True)
JsonLogFormatter.format ─ record.getMessage ─ formatException ─ _extra_context ─ _is_json_scalar ─ json.dumps
PipelineCommandRegistry.runner_for ─ dict.get ─ ValueError ;  names ─ tuple(dict)
PipelineStep.run ─ logger.info×2 ─ _run_step* ─ name* ─ logger.exception (*abstract)
DatasetLoader.load / DatasetWriter.write ─ protocol stubs — 0 implementers
RegressionMetricCalculator.calculate ─ _require_same_length ─ _mae ─ _rmse ─ _r2 (fsum,sqrt,zip)
RegressionMetrics.require_within ─ ValueError ×2
```

Unreachable-by-consumer: `datasets.py` (whole module), `PipelineStep`,
`evaluation.py:85` (TSS==0 r2 branch — also uncovered by tests).

## Boundary table

| Boundary | Where | Faked as | Test |
|---|---|---|---|
| filesystem read | config.py:16 `read_text` | real FS via `tmp_path` | test_config.py:9 |
| process-global logging | logging.py:50 `basicConfig(force=True)` | unfaked | none — configure() uncovered |
| wall clock | logging.py:14 `datetime.now(UTC)` | unfaked | timestamp unasserted |
| yaml parse | config.py:16 `safe_load` (safe variant ✓) | — | ✓ |
| network/subprocess/env/RNG/secrets/pickle | — none — | | |

## Dimension findings

| Dim | Suspect / measured | Evidence | Disposition |
|---|---|---|---|
| D1 | r2 constant-actual: perfect and garbage predictions both → 0.0 | evaluation.py:84-85; `calculate([1]*3,[1]*3).r2==0.0`; sklearn `r2_score` same input → 1.0/0.0 | **G-01 S1** |
| D1 | `extra=` keys (`level`,`logger`,`timestamp`,`exception`) overwrite reserved JSON fields — not in `_LOG_RECORD_KEYS`, not filtered | logging.py:21,28-34; demo: `level='SPOOFED'` in output of an ERROR record | **G-02 S3** |
| D1 | non-scalar `extra` silently dropped (no str() fallback) | logging.py:33,36-37; demo: `run_id=object()` absent from output | **G-03 S3** |
| D8/D1 | `resolve("../../etc")` escapes root; no `is_relative_to` check — violates "repository-relative" contract | paths.py:14-19; demo → `/tmp/etc` from root `/tmp/au01/repo`; trust boundary = config author (repo-committed yaml) | **G-04 S3** |
| D1 | absolute-path branch skips `.resolve()` — returns `/a/../b` unnormalized; asymmetric with relative branch | paths.py:16-17; demo | **G-05 S3** |
| D1 | YAML non-str keys coerced `str(key)` — `{1:.., "1":..}` collides silently; `on:`/`true:` YAML-1.1 keys become `"True"` | config.py:19-20; demo `{'1': 'string'}` | **G-06 S3** |
| D1 | `self.name` read outside try — a raising `name` yields zero log lines (started/failed invariant broken) | pipeline.py:43; demo: RuntimeError from `name`, `logger.records==[]` | **G-07 S3** |
| D3 | `cast(object,…)` / `cast(dict[object,object],…)` — preceded by isinstance narrowing; boundary honest | config.py:15-19 | clean (ADR-0004) |
| D4 | `datasets.py` protocols + `PipelineStep` — speculative API, 0 implementers/subclasses (grep count); prior QF-6 vulture triage already called the protocols "interface contract" — context for triage, not a design verdict | datasets.py:8-27, pipeline.py:32 | **G-08, G-09 S3** |
| D4 | `PipelineCommandRegistry`, `MlopsLoggingConfigurator`, `RegressionMetricThresholds` — vary across 3 real consumers | — | clean, abstractions earn place |
| D2 | `calculate` O(n): 0.06 ms @10², 3.46 ms @10⁴, 477 ms @10⁶ (~5 fsum passes + 2 tuple copies) | probe | clean — constant factor acceptable at real sizes |
| D2 | `format` O(record dict), `runner_for` O(1), `load` O(file) | reading | clean |
| D6 | no stores/caches/registries retained; `dict(runners)` copy | tracemalloc 2000 calls @n=1000: current 0.00 MB, peak 0.06 MB | clean |
| D7 | `format`/`runner_for` stress: 8 threads × 1000 ops, 0 errors; `configure` once-per-process at CLI main (nyc_taxi cli.py:69) — single-threaded by construction | probe | clean |
| D8 | `safe_load` ✓; no subprocess/shell/pickle/secrets; FileNotFoundError propagates unshaped (acceptable) | reading config.py:16 | clean except G-04 |
| D9 | AAA shape + named fakes (SpyPipelineStep, StrictRegressionThresholds) ✓ — but r2 never asserted; no boundary test; mutants survive | see Measurements | **G-10 S4** |
| D10 | no features/ — leaf library, no user-facing surface; consumers' bdd (`predict.feature` ×2) exercise it transitively | find | clean — consumer-side surface is AX-2's matrix |

Suspect not promoted: formatter stamps format-time (`datetime.now`) not
event-time (`record.created`) — defensible; revisit only if queued handlers
appear.

## Measurements

- D2 `calculate` timeit (3 reps): n=10²→0.06 ms, 10⁴→3.46 ms, 10⁶→477.45 ms
  (~137× per 100× — cache effects, still linear order; 5 fsum passes at
  evaluation.py:69,73,80,81,87).
- D6 tracemalloc, 2000 calls @n=1000: current=0.00 MB peak=0.06 MB — no
  retention.
- D7 threading stress, 8×(500×2) ops on shared `runner_for`+`format`: 0
  errors.
- D9 mutation checks (temp edit → pytest → revert):
  - `evaluation.py:89` `1 - rss/tss` → `rss/tss` — **survived** (11 green;
    r2 asserted nowhere).
  - `evaluation.py:22` `>` → `>=` — **survived** (no boundary test).
  - `pipeline.py:45` `_run_step()` → `pass` — **killed** (suite is not
    vacuous).
- Coverage misses (14 stmts): evaluation.py:26-27 (rmse reject), :85
  (TSS==0); logging.py:20 (exc_info), :48-50 (configure body);
  paths.py:17 (absolute), :23 (root_path); pipeline.py:46-50 (failure
  branch), :56/:60 (abstract stubs — uncoverable).

## Gaps promoted

| Gap ID | Severity | One-line |
|---|---|---|
| G-01 | S1 | r2==0.0 on constant actual regardless of fit — diverges from sklearn convention (1.0 perfect / 0.0 wrong), perfect and garbage indistinguishable |
| G-02 | S3 | `extra=` keys overwrite reserved JSON fields (`level`,`logger`,`timestamp`,`exception`) |
| G-03 | S3 | non-scalar `extra` values silently dropped |
| G-04 | S3 | `resolve()` escapes root — no containment check |
| G-05 | S3 | absolute-path branch returned unnormalized |
| G-06 | S3 | YAML non-str keys silently coerced — collision + YAML-1.1 bool keys |
| G-07 | S3 | `name` read outside try → no failure log when property raises |
| G-08 | S3 | `datasets.py` protocols — zero implementers repo-wide |
| G-09 | S3 | `PipelineStep` — zero consumer subclasses repo-wide |
| G-10 | S4 | r2 unasserted, no boundary test, 6 uncovered branches (mutation M1/M2 survived) |

## Spike calibration (MA-1 step 2)

276 src LOC audited in one session: reading ~20 min, measurement scripting
~25 min, 11 suspects → 10 measured rows. Ratio ≈ 1 session / ~300 LOC at
this density — but LOC isn't the driver; symbol count and suspect count are.
L items (~1400–1600 LOC, pre-split by plane) carry proportionally more
suspects but stay single-session if suspects-per-LOC holds ≤ this package's
rate (findings are front-loaded in small shared code). **Verdict: no
re-split needed**; AU-05 and AU-20…AU-26 keep current boundaries, with
the option to split mid-session if a plane exceeds ~30 suspects.
