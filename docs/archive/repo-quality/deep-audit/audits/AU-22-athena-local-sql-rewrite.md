# AU-22 — athena-local SQL rewrite plane audit (2026-10-07)

Scope: `dialect.py` (387), `sql_lexing.py` (196), `hive_types.py` (206),
`external_table.py` (493), `partition_alter.py` (203) — 1485 LOC measured
(`radon raw`; 1031 SLOC). Upstream reuse: AU-20's dispatch/error-funnel and
single-threaded-by-construction verdicts, AU-27's wiring-pattern (D4) verdict,
AU-21's store contracts — the rewrites are pure functions between those planes.
Downstream consumers (`submission.py`, `iceberg.py`, `prepared_execution.py`,
`artifacts.py`, `output_targets.py`, `statement_classification.py`) are
AU-23/AU-24/AU-25 scope; the shared `sql_lexing` helper contracts are verified
here. Permanent contracts: `docs/athena-emulator/adr/0003` (in-memory control
plane), `0007` (result artifacts), `0008` (JSON-1.1 parity), `0009` (async
execution). Parity references: vendored
`research_repos/aws-cli/.../athena/2017-05-18/service-2.json` (`QueryString`
262144), awswrangler `athena/_utils.py` (DESCRIBE/SHOW CREATE/MSCK/UNLOAD
spellings, `generate_create_query`), AWS UG `create-table.html` /
`alter-table-add-partition.html` (fetched 2026-10-07), trino.io hive connector
(procedures, system tables).

## Surface inventory

| Module | Public symbols | Entry points |
|---|---|---|
| `dialect.py` | `to_trino_dialect`, `unload_trino_submission`, `UnloadSubmission` | ★`to_trino_dialect` (submission.py:316), ★`unload_trino_submission` (submission.py:280) |
| `sql_lexing.py` | `IDENTIFIER_PART`, `split_target`, `identifier_name`, `sql_literal`, `quoted_identifier`, `literal_value`, `split_top_level`, `balanced_span`, `string_end`, `quoted_end`, `quoted_pair`, `skip_ws`, `strip_comments` | shared lexer — consumed by all four sibling modules + iceberg/prepared-execution/artifacts/output-targets/statement-classification |
| `hive_types.py` | `HiveColumn`, `hive_type_to_trino`, `hive_column_defs` | consumed by `external_table.py:23`, `iceberg_table.py:36-37` |
| `external_table.py` | `external_table_trino_ddl` | consumed by `dialect.py:54` |
| `partition_alter.py` | `AddPartitionCall`, `add_partition_trino_call` | ★`add_partition_trino_call` (submission.py:287) |

## Callgraph

```
SubmissionPlanner.plan (submission.py:247)
  submit_query = request.resolved_statement or request.query   ← raw text, NOT comment-stripped
  → _map_statement (:248)
      → unload_trino_submission (dialect.py:257)
          → _parse_unload → balanced_span / string_end / _parse_unload_with
            → _with_properties → split_top_level
          → _unload_table_properties / _unload_session_properties
      → add_partition_trino_call (partition_alter.py:87)
          → _parse → split_target/identifier_name → _partition_spec
            → split_top_level/_SPEC_PAIR/_spec_value → _partition_tail
      → _mapped_dialect (:297) → iceberg_trino_submission (AU-23) or identity
          → to_trino_dialect (dialect.py:173)
              → _DATABASE_STATEMENT → _schema_replacement
              → _UTILITY_STATEMENT → _utility_replacement
              → external_table_trino_ddl (external_table.py:115)
                  → _parse → _parse_head → _column_list → hive_column_defs
                    → _split_defs → _parse_type ⇄ _complex_type/_type_list/_struct_type
                  → _match_clause → _CLAUSE_MATCHERS (comment/partitioned/clustered/
                    row/stored/with/location/tblproperties)
                  → _check_required → _emit → _resolve_format/_with_properties
              → _SHOW_PARTITIONS_STATEMENT → _show_partitions_replacement
              → _MSCK_STATEMENT → _msck_replacement
```
Unreachable-looking code: none — vulture's 7 flags on these files are all
cross-module consumers (entry fns called from `submission.py:280,287,316`;
`strip_comments`/`quoted_end` from `statement_classification.py:23`,
`artifacts.py:35`, `output_targets.py:29`, `prepared_execution.py:39`;
`cleanup_table`/`noop_if_exists` read at `submission.py:285,291`).

## Boundary table

| Boundary | Where | Faked as | Test |
|---|---|---|---|
| uuid4 temp-table name (UNLOAD CTAS) | `dialect.py:286` | real (format pinned by regex, value unpinned) | `test_dialect.py:311-317` |
| none else — the plane is pure text→text/None functions | — | — | — |

No filesystem, network, subprocess, env, time, or RNG boundary in the plane;
every input arrives as a `str` and every output is a `str`/dataclass/None.

## Dimension findings

| Dim | Suspect / measured | Evidence | Disposition |
|---|---|---|---|
| D1 | **Comment-blind lexers on the un-stripped submit path** — `balanced_span`/`split_top_level` skip only string literals (no comment awareness) and the rewrite input is raw `request.query` (`submission.py:247` — `strip_comments` runs only in the classification/artifacts planes). A comment containing `(`/`)` inside a column list, partition spec, or UNLOAD inner query — or any comment between UNLOAD's `)` and `TO` — misaligns the span or fails the `\s*to\s*'` match, the rewrite bails to None, and the raw statement reaches Trino, which rejects the `CREATE EXTERNAL TABLE`/`UNLOAD`/`ADD PARTITION` grammar real Athena accepts | probes P-1a…P-1e below; `sql_lexing.py:98-121`, `:68-95`, `dialect.py:345-347` | **G-261 (S3)** |
| D1 | **`_parse_type` recursion overflows on deep Hive types** — 331 nested `array<` (a 2338-char query, cap 262144) raises `RecursionError`, violating the module contract ("not a parseable type returns None so the caller can pass the statement through", `hive_types.py:8-10`); the dispatch funnel converts it to `InternalServerException` (`dispatch.py:170-187`) where real Athena 400s unparseable DDL | bisection probe P-2 (OK at 330, RecursionError at 331); `hive_types.py:120-192` mutual recursion | **G-262 (S3)** |
| D1 | `DROP DATABASE IF EXISTS x` — the `_DATABASE_STATEMENT` middle group only allows `IF NOT EXISTS`, but the missing end-anchor lets bare `if` parse as the identifier, and the rewrite emits `DROP SCHEMA IF EXISTS x` — accidentally correct; all four spellings (create/drop × if-exists/if-not-exists) land on matching Athena/Trino verdicts, including the invalid ones both reject | probes P-3a…P-3f; `dialect.py:70-74` | Closed — verdicts match (fragile-by-accident, report note) |
| D1 | `literal_value` accepts an unbalanced `'a''` tail (`→ a'`) | `sql_lexing.py:61-65`; probe P-4a | Closed — unreachable: every call site pre-verifies balance (`_SPEC_PAIR` grammar, `string_end` on locations, `balanced_span` over WITH spans — probes P-4b/P-4c) |
| D1 | `split_top_level` silently drops the tail after an unterminated string (`"a,'unt"` → `['a', '']`) | `sql_lexing.py:76-80`; probe P-8a | Closed — all four callers reject the truncated pairs downstream (`_with_properties` empty-value arm, `_SPEC_PAIR`, `quoted_pair`, `_IDENTIFIER` check) |
| D1 | Duplicate UNLOAD WITH keys: last wins silently (`format='PARQUET', format='ORC'` → ORC) | probe P-5d | Suspect — report only (real-Athena behavior unverifiable from vendored material) |
| D1 | `unload_trino_submission` returns None (pass-through → Trino rejects the UNLOAD keyword) when `database is None` — real Athena needs no database context for an UNLOAD whose inner query is schema-less | `dialect.py:271`; probe P-7 | Suspect — report only (documented limitation: the stack's Glue has no `default` database to host the temp table, `dialect.py:263-266`) |
| D1 | `ALTER TABLE … DROP PARTITION` passes through (Trino rejects) — real Athena accepts | `partition_alter.py:126-128` (`_ADD` requires `add`) | Suspect — report only (no vendored consumer emits it; awswrangler/terraform/CLI examples all use ADD) |
| D2 | `hive_column_defs` 0.73/8.79/134.48 ms at n=10²/10³/10⁴ columns (slopes ≈1.08/1.19 — mildly superlinear from per-def slicing, ~0.9 s at the 262144-char cap); `split_top_level` 0.42/4.60/51.10 ms (slope ≈1.04); `to_trino_dialect` passthrough <0.01 ms at every size (anchored regexes fail at the head, work proportional to the token count) | timeit table below | Linear-enough, bounded by QueryString — innocent |
| D3 | No `cast`/`Any`/`type: ignore` in the five files (grep clean); `setattr(acc, match.lastgroup or "", raw)`'s `or ""` is defensive-never-taken (the `_DELIMITED_CLAUSE` groups are a closed alternation — exactly one matches); `_UnloadParts.properties: dict[str, str]` honestly types a raw-fragment map | grep + `external_table.py:283-310` | Honest |
| D4 | Pure-function modules at real seams: the rewrites take `(query, database)` and return values; no registry, no DI ceremony; the `sql_lexing` helpers are a genuine shared vocabulary (10 consumer modules) | reading + consumer grep | Earns their place (AU-27 verdict pattern) |
| D5 | `external_table.py` 493 LOC (< 500); `unload_trino_submission` spans 40 lines (`dialect.py:257-296`, 27-line body — a linear guard chain, 2-param signature, no field-multiplication coupling) | measured spans | Report note — no demonstrated harm, no row (§8 anti-churn) |
| D6 | No state to retain: module level holds only immutable constants (regex patterns, frozenset, dict literals, one str) — no `lru_cache`, no registries; dataclass instances are per-call | grep + reading | Clean |
| D7 | Single-threaded by construction (AU-20 verdict reused: async route → event loop, sync handlers await-free, `dispatch.py:166-167`) + corroboration: 8 threads × 500 ops × 4 rewrites = 16 000 calls, 0 errors, deterministic outputs | stress below | Holds |
| D8 | Injection surface bounded: emitted CALL/CTAS arguments are `sql_literal`/`quoted_identifier`-escaped (`dialect.py:138-141,166-170,287-291`, `partition_alter.py:189-203`) — backtick `; DROP TABLE x` and `x''-- ` values land as escaped literal text (probes P-9a/P-9b); verbatim `partitioned_by`/`field_delimiter` WITH values cannot escape the balanced WITH span (an unbalanced `)` ends the span early and fails the tail check — probe P-5a stays inside the parens, Trino rejects the property); the `nosec B608` at `dialect.py:167` remains honest (inputs are anchored-grammar identifier parts, `""`-escaped) | probes P-5a, P-9a…P-9c | Clean |
| D9 | Coverage (full suite — unit+bdd+in-process integration — plane-scoped): 778 stmts, 51 missed, 93.4%; every missed line is a reject bail-out (`return None`/`break`/`continue` guard arm), main-path logic 100% | coverage table below | **G-263 (S4)** |
| D9 | Mutation battery 6/6 killed on main paths (one per module) + 2 survivors on uncovered guard arms: M7 empty-WITH-value arm (`dialect.py:385`) and M8 `CLUSTERED BY` identifier check (`external_table.py:248`) — flipping either leaves the full suite green | battery below | **G-263 (S4)** |
| D10 | No SQL-plane feature file, but 24 integration tests across 4 live-stack suites pin the consumer-visible behavior (external-table DDL readback + partition discovery, UNLOAD registration, ALTER ADD PARTITION, awswrangler partitioned writes); the rewrites' unit suites (62+57+28+12 tests) pin exact emitted text | `tests/integration/test_external_table.py` (3), `test_unload_consumer.py` (6), `test_alter_add_partition.py` (7), `test_awswrangler_consumer_partitioned.py` (8) | Good depth |

## Measurements

**P-1 — comment-blindness** (rewrite-level; submit path does not strip comments):

| probe | result |
|---|---|
| `CREATE EXTERNAL TABLE t (a int /* ) */) LOCATION 's3://x/'` | pass-through verbatim → Trino rejects the grammar |
| `CREATE EXTERNAL TABLE t (a int -- )\n) LOCATION 's3://x/'` | pass-through verbatim |
| `UNLOAD (SELECT 1 /* ) */) TO 's3://x/'` | None → pass-through |
| `UNLOAD (SELECT 1) /* x */ TO 's3://x/'` | None → pass-through (comment before `TO`) |
| `ALTER TABLE t ADD PARTITION (a='1' /* ) */) LOCATION 's3://x/'` | None → pass-through |
| canonical (no comment) control | all three rewrite correctly |

**P-2 — recursion depth** (`CREATE EXTERNAL TABLE t (a array<…array<int>…>) LOCATION …`):
bisection — OK at 330 nested `array<`, `RecursionError` at 331 (query length
2338 chars; model cap 262144). Funnel: `dispatch.py:170-187` →
`InternalServerException("Internal error processing StartQueryExecution")`.

**P-3 — DATABASE spellings** (`to_trino_dialect`):

| input | output |
|---|---|
| `DROP DATABASE IF EXISTS x` | `DROP SCHEMA IF EXISTS x` (valid Trino — `if` parsed as the identifier) |
| `drop database if exists x` | `drop schema if exists x` |
| `CREATE DATABASE IF NOT EXISTS \`db\`` | `CREATE SCHEMA IF NOT EXISTS "db"` |
| `CREATE DATABASE db; DROP TABLE x` | `CREATE SCHEMA db; DROP TABLE x` — tail kept, Trino rejects multi-statement (Athena rejects too) |
| `CREATE DATABASE \`a\`b` | `CREATE SCHEMA "a"b` — Trino rejects (Athena rejects the backtick-in-backtick too) |
| `DROP DATABASE \`x\`` | `DROP SCHEMA "x"` |

**P-4 — literal_value**: `literal_value("'a''")` → `a'` (unbalanced accepted at
the helper level); `UNLOAD … WITH (format='PARQUET''` → None (balanced_span
rejects the unbalanced WITH span first); canonical WITH → correct CTAS. The
lenience is unreachable through every call site.

**P-5 — UNLOAD WITH values**: `partitioned_by=(SELECT 1) AS x` emitted verbatim
inside the WITH parens (`WITH (…, partitioned_by=(SELECT 1) AS x)`) — no
escape; `field_delimiter=','` → `textfile_field_separator=','`; unknown key →
shaped 400 naming it; duplicate `format` keys → last wins (ORC).

**P-6 — CLUSTERED BY**: plain `CLUSTERED BY (a) INTO 2 BUCKETS` →
`bucketed_by=ARRAY['a'], bucket_count=2`; with `SORTED BY (a)` → pass-through.
AWS UG `create-table.html` synopsis (fetched 2026-10-07) documents
`[CLUSTERED BY (col_name, …) INTO num_buckets BUCKETS]` with **no** `SORTED BY`
clause — the `external_table.py:250` comment ("SORTED BY … aren't AWS-valid")
is correct; suspect closed.

**P-7 — UNLOAD without database**: `unload_trino_submission("UNLOAD (SELECT 1) TO 's3://x/'", None)` → None.

**P-8 — split_top_level tail drop**: `"a,'unterminated"` → `['a', '']`.

**P-9 — emitted-SQL injection probes**: ``ALTER TABLE `db`.`t; DROP TABLE x`
ADD PARTITION (a='1')`` → `CALL system.register_partition('db','t; DROP TABLE
x',ARRAY['a'],ARRAY['1'])` (literal text, no escape); `a='x''-- '` →
`ARRAY['x''-- ']`; bare numbers `year=2020, ratio=20.5` →
`ARRAY['2020','20.5']` (string-quoted, procedure-correct).

**D2 — scaling** (min-of-3 × 1 iteration):

| n | `hive_column_defs` | `split_top_level` | `to_trino_dialect` passthrough |
|---|---|---|---|
| 100 | 0.73 ms | 0.42 ms | <0.01 ms |
| 1000 | 8.79 ms | 4.60 ms | <0.01 ms |
| 10000 | 134.48 ms | 51.10 ms | <0.01 ms |

**D7 — stress**: 8 threads × 500 iterations × 4 rewrites (DATABASE, MSCK,
UNLOAD, ADD PARTITION) = 16 000 calls → 0 errors, all outputs byte-identical
to the single-threaded results.

**Coverage** (full suite: unit + bdd + in-process integration, plane-scoped):

| module | stmts | missed | % | missed lines |
|---|---|---|---|---|
| `dialect.py` | 148 | 4 | 97% | 350, 368, 383, 385 |
| `external_table.py` | 288 | 27 | 91% | 152, 170, 218, 227, 230, 233, 243, 246, 249, 264, 269, 273, 280, 308, 325, 342, 349, 362, 365, 375-379, 387, 390, 393, 396 |
| `hive_types.py` | 132 | 15 | 89% | 69, 72, 104, 113, 124, 134, 139, 147, 152, 164, 170, 181, 184, 191, 198 |
| `partition_alter.py` | 101 | 3 | 97% | 118, 155, 176 |
| `sql_lexing.py` | 109 | 2 | 98% | 79, 161 |
| **plane** | **778** | **51** | **93.4%** | all reject bail-out arms |

**Mutation battery** (fail-then-revert; targeted suite first, survivors
re-run against the full suite):

| Mutant | Flip | Result |
|---|---|---|
| M-1 | `_schema_replacement` case-preservation dropped (always `schema`) | KILLED (`test_dialect.py`) |
| M-2 | `_msck_replacement` drops the `'ADD'` mode arg | KILLED (`test_dialect.py`) |
| M-3 | `_resolve_format` default `TEXTFILE`→`ORC` | KILLED (`test_external_table.py`) |
| M-4 | `_TYPE_RENAMES` drops `string`→`varchar` | KILLED (`test_external_table.py`) |
| M-5 | `partition_alter._emit` drops the LOCATION 5th arg | KILLED (`test_partition_alter.py`) |
| M-6 | `_quoted_scan` doubled-quote skip `+= 2`→`+= 1` | KILLED (`test_sql_lexing.py`) |
| M-7 | `_with_properties` empty-value arm accepts (`return None`→`continue`) | **SURVIVED** (full suite) |
| M-8 | `_match_clustered_by` identifier check dropped | **SURVIVED** (full suite) |

M-7/M-8 are the G-263 evidence: both arms are in the uncovered set, and both
flips produce wire-visible wrong output (`WITH (format=)` → shaped-400-instead-
of-passthrough; `CLUSTERED BY (1abc)` → `bucketed_by=ARRAY['1abc']`) that
nothing asserts.

**Report notes (no row)**: `_DATABASE_STATEMENT`'s missing end-anchor is
fragile-but-accidentally-correct (P-3) — a future tightening must keep
`DROP … IF EXISTS` working; `SHOW CREATE VIEW` on an unquoted name is a
no-op rewrite by design (only backticked references need normalizing);
`_show_partitions_replacement` emits columnar rows where real Athena renders
`key=value` — the shape-vs-content delta AWS's docs accept (docstring,
`dialect.py:149-153`); `to_trino_dialect`'s rewrite order (DATABASE → UTILITY
→ external → SHOW PARTITIONS → MSCK) has no overlapping prefixes.

## Gaps promoted

| Gap ID | Severity | One-line |
|---|---|---|
| G-261 | S3 | Comment-blind lexers on the un-stripped submit path — a comment containing `)` (or sitting before UNLOAD's `TO`) breaks all three rewrites into pass-through, so legal-Athena DDL dies on Trino's grammar rejection |
| G-262 | S3 | `_parse_type` recursion overflows at 331 nested `array<` (2338 chars, cap 262144) → `RecursionError` → `InternalServerException` where the module contract is pass-through and real Athena 400s |
| G-263 | S4 | Guard-arm test depth: 51/778 plane stmts uncovered (all reject bail-outs); M-7 (empty-WITH-value) and M-8 (CLUSTERED-BY identifier check) mutants survive the full suite |
