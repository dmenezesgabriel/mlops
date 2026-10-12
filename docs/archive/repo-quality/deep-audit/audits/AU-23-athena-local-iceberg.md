# AU-23 — athena-local iceberg plane audit (2026-10-07)

Scope: `iceberg.py` (457), `iceberg_table.py` (393), `iceberg_probe.py` (93) —
943 LOC measured (`radon raw`; 628 SLOC). Upstream reuse: AU-22's
`sql_lexing` helper contracts (`balanced_span`, `split_top_level`,
`strip_comments`, `quoted_end`, `quoted_identifier`, `sql_literal`) and
`hive_types` verdicts (`hive_column_defs`, `hive_type_to_trino` — G-262's
recursion bound covers this plane's type paths), AU-20's
single-threaded-by-construction and error-funnel verdicts, AU-27's
wiring-pattern (D4) verdict. Downstream: `glue_proxy.py` is AU-25 scope —
the probe's `get_table` is treated as a boundary, faked with the existing
named fakes. Parity references: AWS UG `querying-iceberg-creating-tables.html`,
awswrangler `athena/_write_iceberg.py:108-113,411-426,871-877` (module
docstrings cite both), trino.io iceberg connector (partitioning transforms).

## Surface inventory

| Module | Public symbols | Entry points |
|---|---|---|
| `iceberg.py` | `iceberg_trino_submission` | ★`iceberg_trino_submission` (submission.py:311, via `_mapped_dialect`) |
| `iceberg_table.py` | `iceberg_create_ddl`, `iceberg_alter_ddl`, `ICEBERG_CATALOG`, `ICEBERG_TABLE_TYPE` | consumed by `iceberg.py:47-51`; `ICEBERG_TABLE_TYPE` by `iceberg_probe.py:23` |
| `iceberg_probe.py` | `IcebergTableProbe` (Protocol), `GlueIcebergProbe`, `PROBE_TTL_SECONDS`, `MAX_CACHED_VERDICTS` | ★`GlueIcebergProbe` (main.py:129) |

## Callgraph

```
main.py:129 GlueIcebergProbe(glue) → executor.py:87-98 → SubmissionPlanner
SubmissionPlanner.prepare (submission.py:241)
  submit_query = request.resolved_statement or request.query   ← raw text, NOT comment-stripped
  → _map_statement (:267)
      → unload_trino_submission / add_partition_trino_call (AU-22)
      → _mapped_dialect (:297)
          → iceberg_trino_submission (iceberg.py:65)   [this audit]
              → _backtick_normalize (:429)
                  → _protected_spans (:352) → _span_step (:371)
                      → _literal_step / _identifier_step / _comment_step
                  → _emit_backticks (:442) → quoted_end / quoted_identifier
              → iceberg_create_ddl (iceberg_table.py:87)
                  → _parse (:148) → _parse_head (:162) → hive_column_defs (AU-22 verdict)
                  → _match_clause (:191) → _CLAUSE_MATCHERS (:382)
                      → _match_partitioned_by (:219) → split_top_level (AU-22 verdict)
                      → _literal_matcher (:201) → string_end
                      → _match_tblproperties (:238) → quoted_pair
                          → _apply_iceberg_tblproperties (:263) → _iceberg_format (:280)
                  → _emit_create (:290) → _with_properties (:312) → _partition_entry (:326)
              → _route_iceberg_references (:133)
                  → _table_item_refs (:183) → _scan_item (:211) / _past_item_gap (:228)
                      → _past_noise (:251) / _noise_back (:261) → _covering_span (:272)
                  → _schema_arg_from (:307) → _word_back (:281)
                  → _route_ref (:159) → _resolve (:336) → probe.is_iceberg_table
                      → GlueIcebergProbe.is_iceberg_table (iceberg_probe.py:72)
                          → _read (:87) → GlueProxy.get_table   ← BOUNDARY (AU-25)
                  → _iceberg_qualified (:345) → quoted_identifier
              → iceberg_alter_ddl (iceberg_table.py:108)
                  → _alter_add_columns (:348) → hive_column_defs
                  → _alter_change_column (:364) → hive_type_to_trino (AU-22 G-262 verdict)
              → _invalidate_on_catalog_ddl (:96) → strip_comments (AU-22 verdict)
                  → probe.invalidate
          → to_trino_dialect (AU-22)
```

Unreachable-looking code: none — vulture clean on all three files (rc=0).

## Boundary table

| Boundary | Where | Faked as | Test |
|---|---|---|---|
| moto Glue `get_table` RTT | `iceberg_probe.py:89` | `FakeGlueClient` named fake (`_glue_fakes.py`) | `test_iceberg_probe.py`, `test_iceberg_routing.py:411-441` |
| monotonic clock (TTL) | `iceberg_probe.py:63` | injectable `clock` param, `lambda: now[0]` | `test_iceberg_probe.py:85-96` |
| none else — routing/DDL are pure text→text/None functions | — | `StaticIcebergProbe` named fake (`_iceberg_fakes.py`) | `test_iceberg.py`, `test_iceberg_routing.py` |

No filesystem, network, subprocess, env, or RNG boundary in the plane; the
Glue read is the only external touch and it is Protocol-ported
(`IcebergTableProbe`, `iceberg_probe.py:33-40`).

## Dimension findings

| Dim | Suspect / measured | Evidence | Disposition |
|---|---|---|---|
| D1 | **Comment-blind clause parsing on the iceberg CREATE surface** — `iceberg_create_ddl`'s clause loop consumes comment text as syntax: a comment inside `PARTITIONED BY (…)` is split into garbage partition entries (`cat /* , */ , bucket(16, id)` → `partitioning=ARRAY['cat /*','*/','bucket(id, 16)']` — wire-visible wrong DDL naming nonexistent columns), while comments in the column list, between clauses, or inside TBLPROPERTIES bail the rewrite to pass-through where real Athena accepts the statement. The routing scan (`iceberg.py`) IS comment-aware (`_protected_spans`/`_past_noise`) — only the DDL mapping isn't; it consumes the comment-blind `balanced_span`/`split_top_level` (G-261's surface, here at `iceberg_table.py:181,230,244`) | probes P-1a…P-1f below | **G-264 (S3)** |
| D1 | **Non-table bare identifiers are probed and falsely rewritten on a name collision** — the bare `from` anchor matches the FROM inside `EXTRACT(year FROM ts)`/`TRIM(… FROM s)`, and a leading table-function item (`FROM UNNEST(…) u`) keeps the plain `_REF` probe path — so a column/function name colliding with an Iceberg table name is catalog-qualified into a value-expression position: `EXTRACT(year FROM iceberg."analytics"."ts")` → Trino syntax error on legal Athena SQL | probes P-2a…P-2c; `iceberg.py:104-108` (`_ANCHOR`), `:211-225` (`_scan_item` first-item path), `:159-177` (`_route_ref`) | **G-265 (S3)** |
| D1 | `_backtick_normalize` edges: unterminated backtick, doubled `` `` `` escape, empty ` `` ``, backtick inside a literal — all land on pass-through or correct output; the `close > end` guard (`:451-452`) stops cross-segment spans | probes P-3a…P-3d | Closed (but see G-267: the guard is unasserted — M-3 survives) |
| D1 | `_CATALOG_MUTATING` false-invalidates on a literal containing `; create` (`SELECT '; CREATE TABLE x'` → cache cleared) | probe P-4; `iceberg.py:91-98` | Closed — perf-only (spurious cache clear → extra Glue RTTs, verdicts stay correct); false *retention* has no shape (all mutating leads covered by `test_leading_catalog_verbs_invalidate`) |
| D1 | Bare-ident refs fold to lowercase in the rewrite (`FROM ICE_T` → `iceberg."analytics"."ice_t"`) — Trino folds unquoted identifiers identically; quoted refs preserve case (`identifier_name` unquotes without folding) | `iceberg.py:336-349` | Closed — parity-preserving |
| D2 | **Quadratic comment scaling**: `_covering_span` scans the comment-span list from index 0 on every `_past_noise`/`_noise_back`/`_inside` call, and the item walk calls those O(refs) times → O(refs × comments). Measured 5.95/585.13/32623.40 ms at n=10²/10³/10⁴ comments (slopes ≈2.0/1.74; 187k chars < the 262144 cap) vs linear 2.01/23.28/247.55 ms for plain refs and 1.45/11.29/150.98 ms for backtick normalization | timeit table below; `iceberg.py:272-278` + callers `:251-258, :261-269, :425-426` | **G-266 (S2)** |
| D3 | No `cast`/`Any`/`type: ignore`/`Dict` in the three files (grep clean); `IcebergTableProbe` is an honest structural port; `_IcebergCreate` fields are concretely typed | grep + reading | Honest |
| D4 | Pure-function routing/DDL modules at a real seam + one stateful probe whose cache earns its place (5.9 ms Glue RTT → dict lookup, docstring-measured) behind a 2-method Protocol the executor injects (None-able for probe-free paths) | reading + AU-27 verdict pattern | Earns their place |
| D5 | Files 457/393/93 LOC (< 500); no C-ranked functions (radon cc clean); names specific (`_route_ref`, `_past_item_gap`, `_schema_arg_from`) | radon cc + reading | Clean |
| D6 | Probe cache bounded: 10 000 verdicts = 3.7 MB tracemalloc steady-state; FIFO eviction pins the map at cap (10 001st probe → size 10 000); TTL bounds bypass-the-emulator staleness | tracemalloc below; `iceberg_probe.py:27-30,72-85` | Clean |
| D7 | Single-threaded by construction (AU-20 verdict reused: async route → event loop, sync handlers await-free; the probe is touched only inside `_mapped_dialect` on the loop) + corroboration: 8 threads × 500 ops × 2 statements = 8000 ops over one shared `GlueIcebergProbe`, 0 errors, deterministic outputs | stress below | Holds |
| D8 | Emitted-SQL escaping verified: `we""ird` re-doubles (`iceberg."analytics"."we""ird"`), `location` literals verbatim-copy preserving `''` escapes, partition entries `sql_literal`-escaped; the `bucket(16, a'b)` shape is invalid Hive (unterminated literal) and passes through unrewritten | probes P-5a…P-5c | Clean |
| D9 | Coverage (full suite — unit+bdd+in-process integration — plane-scoped): 439 stmts, 21 missed, 95% — every missed line a reject bail-out arm on invalid input (trailing comma, malformed TBLPROPERTIES pair, unbalanced spans, unparseable columns/type); main-path logic 100% | coverage table below | **G-267 (S4)** |
| D9 | Mutation battery 4/8 killed on main paths; 4 survivors — M-3 unterminated-backtick crossing guard (`iceberg.py:452`), M-4 doubled-backtick unescape (`:454`), M-6 malformed-TBLPROPERTIES reject (`iceberg_table.py:253`), M-7 probe TTL boundary (`iceberg_probe.py:75`, tests use 29/31 s, never exactly 30) — all flips wire-visible and nothing fails | battery below | **G-267 (S4)** |
| D10 | No iceberg feature file — the routing is internal (the user-facing surface is StartQueryExecution, covered by `query_executions.feature`); 5 live-stack integration tests pin the awswrangler consumer shapes (to_iceberg register+insert, comma join, delete/merge, SHOW TABLES FROM, append) | `tests/integration/test_iceberg_consumer.py` (5 tests); AU-22 verdict pattern | Good depth |

## Measurements

**P-1 — comment-blind clause parsing** (`iceberg_create_ddl` via routing):

| probe | result |
|---|---|
| `CREATE TABLE `t` (`id` bigint /* ) */) LOCATION … TBLPROPERTIES(…ICEBERG…)` | pass-through → Trino rejects the grammar |
| `… (`id` bigint -- )\n) …` | pass-through |
| `… (`id` bigint) /* c */ LOCATION …` | pass-through |
| `… PARTITIONED BY (cat /* , */ , bucket(16, id)) …` | **mis-rewrite**: `partitioning=ARRAY['cat /*','*/','bucket(id, 16)']` — comment fragments become partition columns |
| `… TBLPROPERTIES ('table_type'='ICEBERG' /* , */)` | pass-through |
| canonical control (no comment) | rewrites correctly |

**P-2 — false probe on non-table identifiers** (iceberg tables seeded `ts`, `s`):

| probe | result |
|---|---|
| `SELECT EXTRACT(year FROM ts) FROM ice_t` | `EXTRACT(year FROM iceberg."analytics"."ts")` — broken SQL |
| `SELECT TRIM(LEADING 'x' FROM s) FROM ice_t` | `TRIM(LEADING 'x' FROM iceberg."analytics"."s")` — broken SQL |
| `SELECT SUBSTRING(s FROM 2) FROM ice_t` | None (digit-leading arg never matches `_REF`) |
| `SELECT * FROM UNNEST(ARRAY[1]) u` | spurious probe `("analytics","unnest")`; with a colliding iceberg table: `iceberg."analytics"."unnest"(ARRAY[1]) u` |

**P-3 — backtick edges**: `` SELECT * FROM `t `` → pass-through (unterminated
tail left for Trino); `` `we``ird` `` → `"we`ird"` (correct); `` '`x`' ``
literal untouched; ` `` ` ``, empty → pass-through.

**P-4 — invalidation false-positive**: `SELECT '; CREATE TABLE x'` →
invalidations=1 (perf-only); `SELECT 'x; DROP TABLE y' AS q` → 1; controls:
real create → 1, plain select → 0.

**P-5 — escaping**: `SELECT * FROM "we""ird"` (iceberg) →
`iceberg."analytics"."we""ird"`; `LOCATION 's3://b/''weird/'` → verbatim in
`WITH (location='s3://b/''weird/')`; `PARTITIONED BY (bucket(16, a'b))` →
pass-through (invalid Hive literal).

**D2 — scaling** (min-of-3, `iceberg_trino_submission` end-to-end):

| n | plain refs | comments between refs | backticked idents |
|---|---|---|---|
| 100 | 2.01 ms | 5.95 ms | 1.45 ms |
| 1000 | 23.28 ms | 585.13 ms | 11.29 ms |
| 10000 | 247.55 ms | 32623.40 ms | 150.98 ms |

Comment slopes ≈2.0/1.74 (quadratic); refs ≈1.03, idents ≈1.13 (linear).
Attribution: `_covering_span` (`iceberg.py:272-278`) scans the comment list
from index 0 per call; `_past_noise`/`_noise_back`/`_inside` call it per
step inside the O(refs) item walk.

**D6 — cache bounds**: tracemalloc over 10 000 distinct verdicts →
3757 KB current, 3759 KB peak; the 10 001st probe evicts (size stays
10 000). Eviction order pinned by `test_oldest_entry_evicts_at_capacity`.

**D7 — stress**: 8 threads × 500 iterations × 2 statements (iceberg-routed
+ plain) = 8000 ops over one shared `GlueIcebergProbe` → 0 errors, outputs
exactly `{None, 'SELECT * FROM iceberg."analytics"."ice_t"'}`.

**Coverage** (full suite: unit + bdd + in-process integration, plane-scoped):

| module | stmts | missed | % | missed lines |
|---|---|---|---|---|
| `iceberg.py` | 205 | 5 | 98% | 201, 216, 221, 392, 452 |
| `iceberg_probe.py` | 38 | 0 | 100% | — |
| `iceberg_table.py` | 196 | 16 | 92% | 169, 183, 186, 194, 209, 212, 224, 227, 233, 243, 246, 250, 253, 351, 354, 375 |
| **plane** | **439** | **21** | **95%** | all reject bail-out arms |

**Mutation battery** (fail-then-revert; survivors re-run against the full
suite with exit-code capture):

| Mutant | Flip | Result |
|---|---|---|
| M-1 | `_route_ref` verdict gate dropped (route every ref) | KILLED (`test_drop_statement_clears_then_next_read_reprobes` + 1) |
| M-2 | `_schema_arg_from` explain/from prefix arm dropped | KILLED (`test_explain_show_tables_from_is_not_probed`) |
| M-3 | `_emit_backticks` unterminated-crossing guard (`:452`) removed | **SURVIVED** (full suite) |
| M-4 | `_emit_backticks` `` `` ``→`` ` `` unescape (`:454`) dropped | **SURVIVED** (full suite) |
| M-5 | `_partition_entry` transform reorder dropped | KILLED (`test_partition_transforms_reorder_to_trino_spelling`) |
| M-6 | `_match_tblproperties` malformed-pair reject (`iceberg_table.py:253`) → `continue` | **SURVIVED** (full suite) |
| M-7 | probe TTL `<`→`<=` (`iceberg_probe.py:75`) | **SURVIVED** (full suite — boundary at exactly `ttl_seconds` never asserted) |
| M-8 | eviction `>=`→`>` (`iceberg_probe.py:78`) | KILLED (`test_oldest_entry_evicts_at_capacity`) |

M-3/M-4/M-6 sit in the uncovered reject arms; M-7 is an unasserted boundary.
All four flips are wire-visible (wrong identifier text, dropped property
validation, stale verdict past TTL) — the G-263 class on this plane.

**Report notes (no row)**: the routing scan is comment-aware where the DDL
mapping is not — a `_map_statement`-level comment strip (G-261's prescribed
fix shape) would cover both surfaces; `test_comma_item_after_table_function_is_probed`
asserts UNNEST is unprobed as a *chained* item while the first-item path
still probes it (folded into G-265's class evidence); `_invalidate_on_catalog_ddl`
runs after the statement's own probes and never on mapping raises (matches
its docstring contract, `iceberg.py:83-90`).

## Gaps promoted

| Gap ID | Severity | One-line |
|---|---|---|
| G-264 | S3 | Comment-blind clause parsing on the iceberg CREATE surface — a comment inside PARTITIONED BY mis-parses into garbage partition entries (wire-visible wrong DDL); comments in the column list/clauses/TBLPROPERTIES bail to pass-through where real Athena accepts |
| G-265 | S3 | Non-table bare identifiers probed as table refs — `EXTRACT(year FROM col)`/`TRIM(… FROM col)`/first-item `UNNEST(…)` are catalog-qualified on an iceberg name collision, breaking legal statements |
| G-266 | S2 | Quadratic comment scaling in the routing scan — `_covering_span` linear-per-call × O(refs) calls: 32.6 s at 10k comments (187k chars, under the 262144 cap) vs 248 ms linear for plain refs |
| G-267 | S4 | Guard-arm test depth: 21/439 plane stmts uncovered (all reject bail-outs); M-3/M-4/M-6/M-7 mutants survive the full suite (unterminated-backtick guard, `` `` `` unescape, malformed-TBLPROPERTIES reject, TTL boundary) |
