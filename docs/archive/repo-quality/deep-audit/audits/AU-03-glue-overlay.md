# AU-03 — docker/moto glue_overlay audit (2026-09-28)

MA-2 step 2. Target: `docker/moto/glue_overlay.py` — single-file moto overlay
(357 LOC / 228 SLOC per radon raw, LLOC 147). Attaches 4 Glue ops Trino needs
to `GlueResponse`, stores stats/UDFs on per-backend `WeakKeyDictionary`s,
patches `_PartitionFilterExpressionCache.get` (blank `Expression` ⇒ no filter;
upstream `4db88f3a4`/`#10122`), wraps `glue_utils._cast` with Hive-type
normalization, and wraps `GlueBackend.create_table`/`update_table` to inject
`iceberg.field.*` column markers. Loaded by `docker/moto/entrypoint.sh` into
the `motoserver/moto:5.1.16` container (compose mounts dir ro at `/docker/moto`).
Gates: pyright strict 0 err, radon 21 blocks all A (avg 2.19), xenon/bandit/
vulture/deptry/ruff/semgrep clean, 10 tests, coverage 78% (30 missed) —
`make quality` green (but see G-26).

## Surface inventory

| Module | LOC | Public symbols | Entry |
|---|---|---|---|
| `glue_overlay.py` | 357 | `apply_overlay`★, `as_string`, `update_/delete_/get_column_statistics`, `resolve_user_defined_functions`, 4 `*_for_table`/`get_user_defined_functions` response handlers, `create_/update_table_with_iceberg_markers`, `_RESPONSE_OPERATIONS` | apply_overlay (entrypoint.sh:7); handlers via moto `call_action` (X-Amz-Target `AWSGlue_20170331.*`) |
| `tests/test_glue_overlay.py` | 271 | 11 test fns + 2 helpers | — |
| `entrypoint.sh` | 7 | — | compose `entrypoint:` |
| `Makefile`/`pyproject.toml` | 37/33 | gates; `moto[server]==5.1.16` pinned | — |

## Callgraph

```
entrypoint.sh ─ apply_overlay ─ setattr GlueResponse ×4 ops (_RESPONSE_OPERATIONS)
              ─ _PartitionFilterExpressionCache.get = _get_filter_expression
              ─ glue_utils._cast = _cast_partition_value
              ─ GlueBackend.create_table/update_table = *_with_iceberg_markers

update_column_statistics_for_table ─ parameters(json.loads body)
  ─ as_string ×2 ─ [isinstance list] ─ cast ─ update_column_statistics
    ─ backend.get_table (EntityNotFound guard) ─ _column_name ×entry ─ store.update
delete_column_statistics_for_table ─ as_string ×3 ─ delete_column_statistics
  ─ get_table ─ stores.get ─ pop
get_column_statistics_for_table ─ as_string ×2 ─ get_column_statistics
  ─ get_table ─ list(store.values())   [ColumnNames param NEVER READ]
get_user_defined_functions ─ _optional_string ─ _pattern(default "*")
  ─ resolve_user_defined_functions ─ _matching_stores (get_database check)
  ─ _matching_functions (fnmatchcase)   [store has NO writer — always []]

PartitionFilter.__call__ (moto) ─ _PARTITION_FILTER_EXPRESSION_CACHE.get
  ─ _get_filter_expression: blank→None else original get → pyparsing expr
Ident/Like eval (moto) ─ glue_utils._cast ← _cast_partition_value
  ─ _normalize_partition_type (split "(", _SCALAR_TYPE_FOLDS) → original _cast
create_table/update_table (moto handler) ─ *_with_iceberg_markers
  ─ _mark_iceberg_columns (table_type=="ICEBERG" → per-col Parameters) ─ original
```

## Boundary table

| Boundary | Where | Faked as | Test |
|---|---|---|---|
| HTTP request body `parameters` (`json.loads(self.body)`, moto responses.py:36) | handlers 157-216 | real moto dispatch — not faked | wire tests via boto3+mock_aws ✓ |
| moto backend store (`glue_backends[acct][region]`) | 166,181,197,209 | real backend per `@mock_aws` | all 10 ✓ |
| Process-global class mutation | apply_overlay 343-357 | — | none (early-return path uncovered, :346) |
| Backend-lifetime stores (WeakKeyDictionary) | 61-66 | fresh backend per mock_aws | implicit |
| moto internals patched (`_cast`, cache.get, create/update_table) | 249-340 | — | via partition-filter tests; marker path untested |
| Container runtime (env `PYTHONPATH`, volume ro) | entrypoint.sh:6-7 | live compose stack | consumer-side per CS-2b3 |
| fs/subprocess/env-vars/RNG/secrets/pickle in module | — none — | | |

## Dimension findings

| Dim | Suspect / measured | Evidence | Disposition |
|---|---|---|---|
| D1 | **Stale statistics resurrect**: `delete_table`/`delete_database` never purge `_column_statistics` — recreate returns fabricated stats | probe: update→delete_table→create→get → 1 stat; drop-db→recreate → 1 stat | **G-20 S1** |
| D6 | Store grows per drop cycle — key count 51 after 50 create/update/drop rounds; long-lived container backend, unbounded under churn | same probe, len(store) | folded into G-20 |
| D1 | **`ColumnNames` ignored**: model requires it (`service-2.json`); handler returns all stored stats | probe: 2 cols stored, request `["c1"]` → `['c1','c2']` | **G-21 S3** |
| D8/D1 | **Non-dict stat entry → HTTP 500**: `entry.get` AttributeError (glue_overlay.py:79) escapes `call_action` (only ServiceException/HTTPException caught) → werkzeug 500; real AWS → 400 | ThreadedMotoServer raw HTTP probe, traceback captured | **G-22 S3** |
| D8 | Sibling guards correct: non-list `ColumnStatisticsList`→400, non-str `DatabaseName`→400, missing key→400, dict-w/o-ColumnName→400, non-str ColumnName→400 | raw-wire probes | clean (paths untested — see G-27) |
| D1 | **`apply_overlay` guard is all-or-nothing on `get_user_defined_functions`** (345): pre-set that one attr → none of the other 3 ops + 3 patches apply → silent missing ops on upstream drift | subprocess probe: `hasattr` → False/False | **G-23 S3** |
| D1 | **`_normalize_partition_type` no case/space fold** (253-261): `VARCHAR(2)` key → 400 `Unknown type : 'VARCHAR'`; `decimal (10,2)` → `decimal ` unchanged | raw-wire probe (registered `VARCHAR(2)`, filtered read) | **G-24 S3** |
| D4 | **Dead UDF store machinery**: `_user_defined_functions` has zero writers — `CreateUserDefinedFunction` unimplemented in moto 5.1.16 (raw wire → 500 `NotImplementedError`); `resolve_*`/`_matching_*`/`fnmatch`/`_pattern`/`_optional_string` unreachable for non-empty result (~45 LOC). `Pattern` default `*` also lenient vs model-required | grep (def :64-66, sole read :134) + wire probe | **G-25 S3** |
| D9 | **Gate drift**: `maintainability` target exists (Makefile:34-35) but is absent from `quality` chain (:37); every `libs/*` Makefile chains it | Makefile diff vs mlops-shared:37 | **G-26 S3** |
| D9 | **Test depth**: 78% cov — uncovered: error raises (:71,:81,:160), empty-store paths (:120,:140-142), non-None `_optional_string`/`_pattern` (:221,:227), whole iceberg block (:299-316,:339-340), apply early-return (:346). Mutants: iceberg `!=`→`==` SURVIVED; list-guard removal SURVIVED; `.strip()` removal KILLED (`"   "` test); `double` fold removal KILLED | coverage + 4 flips | **G-27 S4** |
| D7 | Threaded server (`run_simple(threaded=True)`, server.py:79-83): `WeakKeyDictionary.setdefault` delegates to atomic `dict.setdefault`; inner `dict.setdefault`/`update`/`pop` atomic under GIL — no orphaned store object possible | stress: 300 rounds × 8 threads concurrent first-writes, switchinterval 1e-7 → 0 lost, 0 errors (2400 ops) | clean |
| D1 | Non-str `Expression` (e.g. `5`) → 500 (`int.strip()` :278) — but unpatched moto 500s identically (`parse_string(5)` TypeError escapes the `ParseException` catch) — no regression | raw-wire probe w/ seeded partition | suspect only — wash vs upstream |
| D2 | All ops O(list size): single `store.update`, `list(values)`, `fnmatch` over always-empty store; `parameters` bound once per handler (re-parse per access avoided) | op count | clean |
| D3 | `cast(list[ColumnStatistics],…)` (:164) asserts element type unchecked — the mechanics behind G-22's 500; casts in `_mark_iceberg_columns` each isinstance-guarded; file-scoped `reportPrivateUsage=false` carries its reason (:50-53); `(self, Any)` signatures mirror moto (comment :321-322) | reading + pyright strict 0 | fold into G-22 fix |
| D5 | Names specific, single responsibility per fn, file 357<500; `as_string` public-named helper — nit only | reading | clean |
| D10 | No `features/`; wire surface validated end-to-end by live-stack consumer tests (CS-2b3: CTAS + partitioned reads via Trino/awswrangler). boto3-through-dispatch tests act as the integration layer in-package | docs/athena-emulator backlog | clean; tag AX-2 |

Suspects not promoted (report-only): non-str `Expression` 500 (parity wash vs
unpatched moto — both escape as unhandled); `parameters` property re-parses
body per access (each handler binds once — no hotspot); UDF `DatabaseName`
optional matches the service model (only `Pattern` is required — leniency
folded into G-25); `GetUserDefinedFunctions` ignores `NextToken`/`MaxResults`
(dead path — G-25).

## Measurements

- Baseline: `radon raw` 357 LOC/228 SLOC; `radon cc` 21 blocks all A avg 2.19;
  `pytest --cov` 10 passed, glue_overlay 78% (miss: 71,81,120,140-142,160,221,
  227,299-316,339-340,346), tests 100%; pyright strict 0 err;
  xenon/bandit/vulture/deptry/ruff/semgrep all clean.
- Stale stats (in-process mock_aws + backend introspection): drop+recreate →
  `GetColumnStatisticsForTable` returned 1 pre-deletion stat; drop-db+recreate
  → 1 stat; 50 create/update/drop rounds → `_column_statistics[backend]` holds
  51 keys (50 dead).
- ColumnNames: 2 stats stored (`c1`,`c2`); request `ColumnNames=["c1"]` →
  returned `['c1','c2']`.
- Raw HTTP probes via `ThreadedMotoServer` + urllib with SigV4-scoped
  `Authorization` header: non-list stats → `400 InvalidInputException`;
  non-dict entry → `500` werkzeug HTML (`AttributeError 'str' object has no
  attribute 'get'` at :79); non-str db → 400; missing stats → 400; UDF sans
  DatabaseName/Pattern → `200 []`; `CreateUserDefinedFunction` → `500
  NotImplementedError`; `Expression=5` w/ seeded partition → `500` (:
  278 `int.strip`); `Expression="region = 'US'"` on `VARCHAR(2)` key → `400
  Unknown type : 'VARCHAR'`; garbage expr → `400 Unsupported expression`;
  missing db → `400 EntityNotFoundException`.
- Guard drift (fresh subprocess): set `GlueResponse.get_user_defined_functions`
  then `apply_overlay()` → `update_column_statistics_for_table`,
  `get_column_statistics_for_table` absent → other ops+ patches never attach.
- Iceberg markers (untested code verified functional): iceberg table cols get
  `{'iceberg.field.current':'true'}` ×2; plain table cols `None`; update_table
  path marks too.
- Concurrency: 300 rounds × 8 threads `Barrier`-released concurrent
  first-writes per fresh table, `sys.setswitchinterval(1e-7)` → lost=0,
  errors=0 (2400 ops); `weakref.WeakKeyDictionary.setdefault` →
  `self.data.setdefault(...)` single atomic call.
- Mutations: `!=`→`==` iceberg gate (:300) SURVIVED (10 pass); `isinstance`
  list guard off (:159) SURVIVED; `not expression.strip()`→`not expression`
  (:278) KILLED (`test_empty_expression_returns_all_partitions`);
  `"double"` fold removal (:244) KILLED
  (`test_equality_filter_on_double_partition_key`).

## Gaps promoted

| Gap ID | Severity | One-line |
|---|---|---|
| G-20 | S1 | column statistics survive `delete_table`/`delete_database` — recreated table reads fabricated stats; store grows 1 key per drop cycle |
| G-21 | S3 | `get_column_statistics_for_table` ignores required `ColumnNames` — returns all stored stats |
| G-22 | S3 | non-dict `ColumnStatisticsList` entry → AttributeError → HTTP 500 (real AWS: 400) |
| G-23 | S3 | `apply_overlay` all-or-nothing guard keyed on one op — upstream shipping it disables the whole overlay silently |
| G-24 | S3 | `_normalize_partition_type` lacks case/space fold — `VARCHAR(2)`, `decimal (10,2)` keys 400 on filtered reads |
| G-25 | S3 | UDF store/matching/pattern machinery is unreachable (no writer op exists); ~45 LOC speculative generality |
| G-26 | S3 | `maintainability` missing from `quality` chain (target exists at :34) — drifts below sibling-package floor |
| G-27 | S4 | 22% uncovered incl. whole iceberg block + all error paths; 2/4 mutants survive (iceberg gate, list guard) |

Note: probe harness detail (ThreadedMotoServer + SigV4-shaped header,
`parameter_validation=False` client) recorded here for reproducibility — the
two-layer client SDK validates shapes so the 500 paths are only reachable by
raw HTTP callers.
