# AU-25 — athena-local boundary+artifact plane audit (2026-10-08)

Scope: `trino_client.py` (274), `glue_proxy.py` (374), `s3_writer.py` (190),
`artifacts.py` (224), `output_targets.py` (277), `query_results.py` (192),
`result_shapes.py` (75) — 1606 LOC measured (`radon raw`; 1077 SLOC; max
cyclomatic B(10) on `GlueTableMetadata.to_payload`, a linear optional-member
guard chain). Upstream: AU-20 protocol verdicts (`request_fields`,
`dispatch` error funnel), AU-21 state (`ExecutionStore`,
`QueryExecutionRecord`), AU-22 `sql_lexing` (`strip_comments`,
`string_end`), AU-24 execution (`QueryExecutor` contracts — `StatementClient`,
`ManifestSnapshotSource`, `ResultArtifactWriter` protocols are implemented
here). Downstream: none — this plane is the external-I/O leaf. Parity
references: canonical `service-2.json` (athena, byte-pinned), Trino client
protocol (trino.io `develop/client-protocol.html`), moto
`athena/models.py`/`glue/models.py`, awswrangler `_read.py`/`_utils.py`,
ADR-0001/0005/0006/0007/0008/0009/0010.

## Surface inventory

| Module | Public symbols | Entry points |
|---|---|---|
| `trino_client.py` | `TrinoClient` (`submit_statement`, `fetch_next`, `cancel`), `create_trino_client`, `TrinoPage`, `TrinoColumn`, `TrinoQueryError`, `TrinoTransportError` | ★`main.py` composition root → `QueryExecutor` (`submission.py:434`, `executor.py`) |
| `glue_proxy.py` | `GlueProxy` (`list_databases`, `get_database`, `list_tables`, `get_table`, `delete_table`, `for_endpoint`), `CatalogClient` (Protocol), `GlueDatabase`, `GlueTableMetadata`, `GlueColumn` | ★`catalog_metadata.py` handlers, ★`output_targets.py:104`, ★`iceberg_probe.py` |
| `s3_writer.py` | `S3Writer` (`put_object`, `list_object_paths`, `for_endpoint`), `ObjectStoreClient` (Protocol), `S3WriterError` | ★`artifacts.py` writer, ★`output_targets.py:142` |
| `artifacts.py` | `ArtifactWriter.write`, `artifact_plan`, `ArtifactPlan` | ★`executor.py:362` (ResultArtifactWriter protocol) |
| `output_targets.py` | `OutputSnapshotter` (`capture`, `drop_table`), `OutputSnapshot`, `ManifestTargetError`, `insert_table_reference`, `unload_location` | ★`submission.py:411` (ManifestSnapshotSource protocol), `executor.py:423,439` |
| `query_results.py` | `get_query_results`, `get_query_runtime_statistics` | ★`query_executions.py:373,377` handler bindings |
| `result_shapes.py` | `to_athena_result_shape` | ★`executor.py:345` (cache boundary) |

## Callgraph

```
main.py composition root
  TrinoClient ← QueryExecutor (StatementClient protocol)
    _preflight (submission.py:434) → submit_statement → POST /v1/statement
        → _request (:141) → _should_retry (:165) → _retry_delay (:171)
        → _parse_page (:183) → _parse_columns/_parse_rows/_parse_stats/_parse_error
    _poll_to_end (executor.py:317) → fetch_next (GET nextUri)
    _stop_statement (executor.py:341) → cancel (DELETE nextUri)
  GlueProxy ← catalog_metadata handlers / OutputSnapshotter / iceberg_probe
    _run (:234) → CatalogClient ops → _error_code (:257)
    payload shaping: _database_from_glue (:289) / _table_metadata_from_glue (:306)
        → _objects/:270 _object/:282 _string/:332 _string_map/:337 _epoch/:349 _columns/:358
  S3Writer ← ArtifactWriter / OutputSnapshotter
    put_object (:74) / list_object_paths (:86) → _list_page (:113) → _run (:137)
    _split_s3_path (:155) / _error_code (:163) / _objects (:176) / _string (:188)
  OutputSnapshotter ← SubmissionPlanner._capture_manifest (submission.py:411)
    capture (:64) → _capture_insert (:77) → insert_table_reference (:146)
        → _identifier_tokens (:198) → _qualified_name (:220) → _split_segments/:234 _fold_identifier/:251
        → _resolve_insert_target (:89) → _insert_table_location (:101) → glue.get_table
    capture (:64) → _capture_unload (:117) → unload_location (:164)
        → _scan_unload_location (:177) → _to_clause_at (:257) → _quoted_string_at (:267)
    _snapshot (:139) → s3.list_object_paths
    drop_table (:126) → glue.delete_table  ← executor.py:423,439 (UNLOAD CTAS cleanup)
  ArtifactWriter ← QueryExecutor._complete (executor.py:362)
    write (:91) → artifact_plan (:62) → _write_rows (:108) → _output_prefix (:167)
        → _rows_bytes (:182) / _metadata_bytes (:202)
    write (:91) → _write_manifest (:121) → _manifest_paths (:135)
        → s3.list_object_paths (snapshot diff :148-149 | _external_location :155 → strip_comments + RE :41)
  query_executions handlers
    GetQueryResults → get_query_results (:32) → executor.ensure_query_finished
        → _next_token_offset (:104) → _max_results (:93) → _result_page (:72)
        → _result_set_payload (:127) → _cell_value (:167)
    GetQueryRuntimeStatistics → get_query_runtime_statistics (:62) → store.get
        → _runtime_statistics_payload (:182)
  executor._complete (:345) → to_athena_result_shape (:30)
    → _describe_shape (:48) / _show_create_shape (:70)
```

No unreachable code spotted in-plane. `query_results.py:33` (`store` param)
and `output_targets.py:68` (`catalog` param) are declared but never read —
see G-288.

## Boundary table

| Boundary | Where | Faked as | Test |
|---|---|---|---|
| Trino statement protocol (POST/GET/DELETE) | `trino_client.py` whole module | `httpx.MockTransport` + `ScriptedTrinoHandler`; `ScriptedStatementClient`/`TerminalStatementClient`/`GatedStatementClient` (executor-side named fakes) | `test_trino_client.py`, `test_executor*.py` |
| Glue catalog | `glue_proxy.py:158-172` (`CatalogClient` protocol) | `FakeGlueClient` (named fake w/ `tables` map + error injection) | `test_catalog_metadata.py`, `test_output_targets.py` |
| S3 objects | `s3_writer.py:58-72` (`ObjectStoreClient` protocol) | `RecordingObjectStore` (named fake w/ `objects` map, `put_calls`, `list_error`) | `test_artifacts.py`, `test_s3_writer.py`, `test_output_targets.py` |
| botocore session→client | `glue_proxy.py:165`, `s3_writer.py:65` | real botocore→moto over HTTP (live stack) | `tests/integration/*` |

Both Protocols are thin surfaces at real seams; `for_endpoint` is the only
botocore-session touch per module (the documented designated-boundary
decision — `# pyright: reportMissingTypeStubs=false` scoped to these two
modules). No filesystem/subprocess/env boundary in-plane.

## Dimension findings

| Dim | Suspect / measured | Evidence | Disposition |
|---|---|---|---|
| D1 | **`_external_location` regex reads through string literals and double-quoted identifiers** — it scans comment-stripped but *literal-keeping* SQL (`artifacts.py:41-44,219-224`), so a valid-SQL double-quoted identifier carrying the pattern shadows even a real WITH clause: `CREATE TABLE t AS SELECT 1 AS "external_location = 's3://evil/'" WITH (external_location='s3://real/')` → `'s3://evil/'` → the manifest enumerates a foreign prefix (files the query never wrote, attacker-chosen or accidental); an escaped-quote literal (`COMMENT 'external_location=''s3://e/'''`) before the WITH yields `''` → `S3WriterError` → FAILED on valid SQL. G-261/G-264 class, third site | probes P-1a/b; `artifacts.py:135-164`; module contract `output_targets.py:3-5` ("exactly the files a query wrote") | **G-277 (S1)** |
| D1 | **INSERT/UNLOAD manifests cross-list concurrent writers' files** — the before/after snapshot diff (`artifacts.py:147-149`) counts every key that appeared under the target prefix between pre-submit capture and completion-listing, so a second writer landing files in the window is claimed by this query's manifest: probe: A's manifest lists `a.parquet` **and** `b.parquet` (B's write) — the module's own contract ("tracks the files that the query was responsible for writing", `output_targets.py:3-5`) is violated under any concurrent same-prefix writer | probe P-2; `output_targets.py:139-143`, `artifacts.py:147-149` | **G-278 (S1)** |
| D1 | **`POST /v1/statement` is retried** (`trino_client.py:141-146,165-168`) — 429/502/503/504 or an empty 200 re-POSTs a non-idempotent statement; probe: one `submit_statement` → **2 POSTs**. A 502-after-accept blip double-executes INSERT/CTAS/UNLOAD server-side (duplicate rows, double-written files). The upstream python client never retries statement submission — polling GET/DELETE are the idempotent ops | probe P-3; `trino_client.py:114-117,140-146` | **G-279 (S1)** |
| D1 | **`_next_token_offset` `int()` leniency — G-248 class, second site** — `+3`, ` 3 `, `3 `, `03` all decode to offset 3 → 200; `999999` beyond the rows → 200 with an empty page. Same silent-decode-vs-reject divergence the AU-20 row pinned on `pagination.offset_page` | probe P-4; `query_results.py:104-124` | **G-280 (S3)** |
| D1 | **`_split_s3_path` is scheme-blind** (`s3_writer.py:155-160`) — `removeprefix("s3://")` makes `ftp://host/x`→`('ftp:','/host/x')`, `relative`→`('relative','')`; an `ftp://` OutputLocation is accepted at submit and fails late at artifact write (`Bucket='ftp:'` param-validation) where real Athena 400s `ResultConfiguration` at StartQueryExecution. UNLOAD `TO 'ftp://host/x'` likewise snapshots a non-S3 target | probes P-5, U; `output_targets.py:117-124`, `artifacts.py:167-179` | **G-281 (S3)** |
| D1 | **`S3WriterError` escapes `OutputSnapshotter.capture()` unshaped** — `_snapshot` (`output_targets.py:139-143`) calls `list_object_paths` directly; `submission.py:410-415` catches only `ManifestTargetError`, so a `NoSuchBucket`/transport listing failure surfaces as an unshaped 500 at submit, bypassing the designed `manifest_target_error` degradation (docstring submission.py:393-395: "leaves a reason for the artifact writer instead of failing submit"). Asymmetry verified: the *same* listing failure at write time is wrapped to `ArtifactWriteError` → FAILED (probe W) | probes U/W; `output_targets.py:139-143`, `submission.py:410-415`, `artifacts.py:105-106` | **G-282 (S3)** |
| D1 | **Malformed-page member leniency silently truncates / the ragged-DESCRIBE crash parks the record RUNNING** — `nextUri: 42` → `finished=True` (page chain silently truncated; rows lost on the wire), non-list rows/non-dict columns dropped, `error:"str"` swallowed (a failed statement could read clean); then `_describe_shape` indexes `row[0],row[1],row[3]` unconditionally once the column signature matches (`result_shapes.py:51,56`) — a ragged row → `IndexError` escapes `to_athena_result_shape` → runner dies → `_reap_task` only logs (`executor.py:246-250`) → record parks RUNNING forever | probes P-6/P-7; `trino_client.py:213-218,222-252`, `result_shapes.py:48-67` | **G-283 (S3)** |
| D2 | Linear across the plane (3 sizes, min-of-3): `_rows_bytes` 0.139/1.658/21.488 ms, `_result_set_payload` 0.095/1.300/14.092 ms, `_describe_shape` 0.027/0.256/2.843 ms, `insert_table_reference` 0.030/0.228/2.447 ms, `unload_location` 0.031/0.200/1.783 ms, `_external_location` 0.004/0.033/0.388 ms, `list_object_paths` 0.150/1.541/16.832 ms at n=10²/10³/10⁴ — slopes ≈1.0-1.2, no superlinear arm | D2 battery below | Clean |
| D3 | Every `cast(...)` is post-`isinstance` narrowing at a declared JSON boundary (documented "re-anchor" comments, e.g. `s3_writer.py:163-165`); `cast(CatalogClient/ObjectStoreClient, client)` + `reportMissingTypeStubs=false` + `reportUnknownMemberType` ignore are the scoped designated-boundary decision; no `Any`/`Dict`/untyped fns outside the two botocore Protocols | grep + reading | Honest |
| D4 | Ports at real seams; `ResultArtifactWriter`/`ManifestSnapshotSource` protocols earn their place (executor fakes exist). **Sync boto3 I/O inside async paths** — `capture`, `drop_table`, `write` and the catalog handlers run blocking boto calls inline: measured 52.4 ms capture → **0 event-loop ticks** during it; 3 concurrent 50 ms-latency captures serialize at 154 ms (floor 150). Every moto roundtrip stalls all in-flight requests | P-10; `output_targets.py:64,142`, `artifacts.py:91`, `glue_proxy.py` publics | **G-284 (S2)** |
| D5 | **Retained `OutputSnapshot.before_paths` sets are unbounded per record** — the 10 000-record store cap bounds count, not bytes: independent 1000-key snapshots → +197.4 MB @ 2000 records (≈101 KB/record, 103 B/key); 5000-key → +825.9 MB @ 1000 records (≈846 KB, 173 B/key); cap-math 10k×1000-key ≈ 1001 MB. A busy INSERT/UNLOAD workload on wide prefixes retains ~1 GB for snapshot data already consumed by the write | tracemalloc P-9; `output_targets.py:48`, `artifacts.py:147-149` | **G-285 (S2)** |
| D6 | 200 concurrent `capture` calls over shared fakes → 200 identical snapshots; 200 concurrent `write`s → 400 objects, no torn state (single-loop discipline + frozen dataclasses hold). The loop-stall finding lives under D4. Files 274/374/190/224/277/192/75 LOC, CC ≤ B(10), specific names | P-10 stress arms + radon | Clean (D4 row) |
| D7 | `cancel`→`stop` lifecycle is the executor's (AU-24 verdicts). In-plane: `list_object_paths` bounds truncation loops via the missing-token raise (`s3_writer.py:104-111`); no leak surface. The double-POST retry is D1 (G-279) | reading + P-3 | Clean |
| D8 | Header values to Trino are controlled-shaped: `X-Trino-Catalog` constant, `X-Trino-User` config, `X-Trino-Schema` = wire `Database` — CRLF raises `httpx.LocalProtocolError` (a `TransportError` → shaped unreachable), **but non-ASCII raises bare `UnicodeEncodeError` outside `_send`'s `except` → unshaped 500 at submit**. Malformed Glue `Expression` (`'('`, `'t['`) → `re.error` past `_run`'s boto-only catches → 500 where Glue 400s. `X-Trino-Session` values come only from the controlled codec map; artifact keys are server-owned `{qid}` names under a config prefix | probe P-8; `trino_client.py:102-117,155-162`, `glue_proxy.py:194-199,240-254` | **G-286 (S3)** |
| D9 | Coverage (unit+bdd, plane-scoped): 673 stmts, 19 missed, 97% (full suite covers one extra arm → 18) — every missed line an error/guard arm: `s3_writer` 93% (truncated-no-token, no-bucket, two `_error_code` arms, non-list `_objects`), `glue_proxy` 96% (two `_error_code` arms, `_objects` non-list, `_object` missing-member raise, `_epoch` numeric, `_columns` non-dict skip), `output_targets` 96% (missing INSERT target, unterminated-string `return None`, empty-names `return None`, **`_to_clause_at` word-boundary `return False`** — the M-10 arm, unterminated fallback), `trino_client` 98% (non-dict payload, non-dict stats), `query_results` 98% (non-str NextToken raise); `artifacts`/`result_shapes` 100%. Mutation battery 12/14 killed; **M-6** (`offset < 0`→`<=0`) and **M-10** (alnum word-boundary guard dropped — sits on the uncovered `output_targets.py:263`) survive the *full* suite | P-12/P-13 | **G-287 (S4)** |
| D10 | `artifacts.feature` (5 scenarios — quoted CSV header+sidecar, CTAS manifest, INSERT/UNLOAD appended-files-only) + `query_executions.feature` (3 pagination) + `managed_results`/`canonical_model`; integration suites pin `get_query_results` paginator-merge, artifacts/output_location/unload_consumer/awswrangler live. **Hole: `GetQueryRuntimeStatistics` is unit-only — no live-stack or bdd surface** (registered op on the wire). Stop/batch/list coverage lives in AU-24's report | `tests/bdd/*.feature`, `tests/integration/*` | G-287 note |

## Measurements

**P-1 — `_external_location` on literal/identifier-carried patterns**
(`artifacts.py:219-224`):

| probe | result |
|---|---|
| `… AS "external_location = 's3://evil/'" WITH (external_location='s3://real/')` (alias, valid SQL) | `'s3://evil/'` — **shadows the real property** |
| `("external_location = 's3://evil/'" int) WITH (external_location='s3://real/')` (column name, valid SQL) | `'s3://evil/'` |
| `… AS "external_location = 's3://evil/'"`, no WITH | `'s3://evil/'` |
| `COMMENT 'external_location=''s3://e/'''` before real WITH | `''` → `S3WriterError: S3 URI '' has no bucket` → FAILED |
| `SELECT 'external_location = ''s3://fake/'' '` literal, no WITH | `''` → FAILED |
| control `WITH (external_location='s3://real/')` | `'s3://real/'` |
| control no property | `None` → designed `ArtifactWriteError` path |

End-to-end on the foreign target: manifest artifact lists whatever the
listing returns for `s3://evil/` — files this query never wrote
(`artifacts.py:164` `list_object_paths(target)`).

**P-2 — concurrent INSERT manifest** (`RecordingObjectStore`; A snapshots
`f0.parquet`, then B writes `b.parquet`, then A writes `a.parquet`):

| artifact | bytes |
|---|---|
| `A-manifest.csv` | `s3://data-bucket/events/a.parquet\ns3://data-bucket/events/b.parquet\n` — **B's file claimed** |

**P-3 — statement POST retry** (`ScriptedTrinoHandler` 502→200):

| probe | result |
|---|---|
| requests for one `submit_statement` | `[POST /v1/statement, POST /v1/statement]` — 2 engine statements |

**P-4 — NextToken decode** (`get_query_results`, MaxResults=2, 6 rows):

| token | result |
|---|---|
| `+3` / ` 3 ` / `3 ` / `03` | 200, rows from offset 3, `NextToken='5'` |
| `0x3` / `3.5` / `-3` / `abc` | `InvalidRequestException` 400 |
| `999999` | 200, 0 rows, no NextToken |

**P-5 — `_split_s3_path` + OutputLocation end-to-end**:

| path | result |
|---|---|
| `s3://bucket/key` | `('bucket','key')` |
| `bucket/key` | `('bucket','key')` |
| `ftp://host/path` | `('ftp:','/host/path')` |
| `s3://` | `S3WriterError` |
| `relative` / `a/b/c` | `('relative','')` / `('a','b/c')` |
| `OutputLocation='ftp://host/dir'` SELECT artifact write | `put_object(Bucket='ftp:', Key='/host/dir/{qid}.csv', …)` — accepted into the client call (real boto3 param-validates → `S3WriterError` → `ArtifactWriteError` → FAILED at write time) |

**P-6 — `_parse_page` malformed members** (MockTransport, one 200 doc each):

| shape | result |
|---|---|
| `nextUri: 42` | `finished=True` — chain silently truncated |
| `data: [["a"], 42, {"r":1}]` | `rows=[['a']]` — non-list entries dropped |
| `columns: [{…}, 42]` | one column kept, `42` dropped |
| `stats: [1,2,3]` | `{}` |
| `error: "something failed"` | `error=None` — failure swallowed |
| `updateType: 7` | `update_type=None` |

**P-7 — `_describe_shape` ragged rows** (Trino 4-column signature):

| rows | result |
|---|---|
| `[["a","b","c"]]` | `IndexError: list index out of range` → escapes `_complete` → runner dies → record parks RUNNING (`executor.py:246-250` logs only) |
| `[["a","b"]]` | same |
| `[[], ["x","y","z","w"]]` | same |

**P-8 — Glue `Expression` + Trino header values**:

| probe | result |
|---|---|
| `Expression='t*'` | 1 table |
| `Expression='('` / `'t['` | `re.error` escapes `_run` (boto-only catches) → InternalServerException 500 (real Glue 400s) |
| `schema='bad\r\nInjected: x'` / `'bad\nnewline'` | request proceeds (h11 `LocalProtocolError` ⊂ `TransportError` → shaped on the real socket) |
| `schema='unicode_ß'` | `UnicodeEncodeError` escapes `_send`/`_preflight` → unshaped 500 |

**P-9 — D5 retention** (tracemalloc):

| probe | result |
|---|---|
| 2000 records × shared 1000-key frozenset | +4 095 KB (shared set — ≈2 KB/record overhead) |
| 2000 records × **independent** 1000-key snapshots | **+197.4 MB** (≈101 KB/record, 103 B/key) |
| 1000 records × 5000-key snapshots | **+825.9 MB** (≈846 KB/record, 173 B/key) |
| cap-math 10k records × 1000-key | ≈ **1001 MB** retained |

**P-10 — sync I/O in async paths** (`SlowObjectStore` +50 ms/list):

| probe | result |
|---|---|
| one `capture`, ticker loop running | 52.4 ms elapsed, **0 loop ticks** during it |
| 3 concurrent captures | 154.3 ms — serial floor (3×50 ms) |
| 200 concurrent captures | 200 identical snapshots, no torn state |
| 200 concurrent `write`s | 400 objects (2/execution) |

**P-11 — vestigial parameters + duplication**:

| probe | result |
|---|---|
| `capture(…, catalog)` for `awsdatacatalog`/`iceberg`/`bogus`/`None` | identical `s3://b/p/` — `catalog` never read (`output_targets.py:68`); `INSERT INTO othercat.db.t` resolves `(db,t)` — `_qualified_name` keeps `names[-2:]` and drops the catalog segment (`:231`) |
| `get_query_results(store, executor, payload)` | `store` declared `:33`, never read — record comes from `executor.ensure_query_finished` |
| `_error_code`/`_objects`/`_string` | verbatim-identical across `glue_proxy.py:257-279,332-334` and `s3_writer.py:163-190` — 24 duplicated lines |

**U — UNLOAD `TO` failure shapes through `capture()`**:

| probe | result |
|---|---|
| `TO 'unterminated` | `OutputSnapshot(location='unterminated/', …)` — garbage location snapshotted, no error |
| `TO ''` | `S3WriterError: S3 URI '' has no bucket` — escapes `capture()` |
| `TO 'ftp://host/x'` | `OutputSnapshot(location='ftp://host/x/', …)` |
| `TO 's3://nope/x/'`, NoSuchBucket on list | `S3WriterError … NoSuchBucket` **escapes `capture()`** — not `ManifestTargetError` → submit-time 500 instead of the designed `manifest_target_error` degradation |

**W — write-time asymmetry**: same `NoSuchBucket` on the completion re-list →
`ArtifactWriteError` → FAILED (the designed wrap at `artifacts.py:105-106`).

**D2 — scaling battery** (min of 3, n = 10²/10³/10⁴; slopes from the two
adjacent ratios):

| function | n=100 | n=1000 | n=10000 |
|---|---|---|---|
| `_rows_bytes` (n rows) | 0.139 ms | 1.658 ms | 21.488 ms |
| `_result_set_payload` (n rows, one page) | 0.095 ms | 1.300 ms | 14.092 ms |
| `_describe_shape` (n rows) | 0.027 ms | 0.256 ms | 2.843 ms |
| `insert_table_reference` (n-char query) | 0.030 ms | 0.228 ms | 2.447 ms |
| `unload_location` (n-char inner select) | 0.031 ms | 0.200 ms | 1.783 ms |
| `_external_location` (n-char query, no match) | 0.004 ms | 0.033 ms | 0.388 ms |
| `list_object_paths` (n objects) | 0.150 ms | 1.541 ms | 16.832 ms |

**P-12 — coverage** (unit+bdd, plane-scoped; full suite covers one extra
error arm):

| module | stmts | missed | % | missed lines |
|---|---|---|---|---|
| `trino_client.py` | 129 | 2 | 98% | 200 (non-dict payload), 257 (non-dict stats) |
| `glue_proxy.py` | 161 | 6 | 96% | 262, 265 (`_error_code` arms), 273 (`_objects` non-list), 285 (`_object` missing-member), 354 (`_epoch` numeric), 365 (`_columns` non-dict skip) |
| `s3_writer.py` | 71 | 5 | 93% | 108 (truncated-no-token raise), 159 (no-bucket raise), 168, 171 (`_error_code` arms), 179 (`_objects` non-list) |
| `artifacts.py` | 90 | 0 | 100% | — |
| `output_targets.py` | 142 | 5 | 96% | 82 (missing INSERT target), 185 (unterminated-string `None`), 228 (empty-names `None`), **263 (`_to_clause_at` word-boundary `return False`)**, 272 (unterminated fallback) |
| `query_results.py` | 52 | 1 | 98% | 115 (non-str NextToken raise) |
| `result_shapes.py` | 28 | 0 | 100% | — |
| **plane** | **673** | **19** | **97%** | |

**P-13 — mutation battery** (fail-then-revert; each mutant ran unit+bdd,
the two survivors re-confirmed against the full 1369-test suite; battery
re-run after the first shell harness corrupted its restore chain — all
numbers below are the corrected pass):

| Mutant | Flip | Result |
|---|---|---|
| M-1 | `s3_writer` dir-skip `endswith("/")` inverted | KILLED |
| M-2 | `IsTruncated is not True` → `is True` | KILLED |
| M-3 | empty-200 retry arm dropped | KILLED |
| M-4 | `Retry-After` isdigit guard flipped | KILLED |
| M-5 | pagination end `<` → `<=` | KILLED |
| M-6 | negative-token `<0` → `<=0` | **SURVIVED (full suite)** — no test pins acceptance of a `"0"`-offset token |
| M-7 | DESCRIBE `== "partition key"` → `!=` | KILLED |
| M-8 | manifest set-diff → union | KILLED |
| M-9 | CSV null arm inverted | KILLED |
| M-10 | `_to_clause_at` alnum word-boundary dropped | **SURVIVED (full suite)** — sits on uncovered `output_targets.py:263`; `AUTOTO'x'`-adjacent tokens falsely match |
| M-11 | `_fold_identifier` quote check inverted | KILLED |
| M-12 | capture INSERT/UNLOAD swap | KILLED |
| M-13 | Trino stamp filter `!=` → `==` | KILLED |
| M-14 | `_split_s3_path` bucket guard flipped | KILLED |

**Live stack**: athena :5001 / moto :5000 / trino :8485 all healthy during
the full-suite run (1369 passed, 2 skipped — terraform harness, Go toolchain
absent — in 221 s).

**Report notes (no row)**: `get_query_runtime_statistics` on a RUNNING record
returns 200 with zeroed stats (`query_results.py:188-191` `or 0`) — real
Athena also answers the op on running queries, so the shape holds; the op's
missing live-stack coverage folds into G-287. `del final_page`
(`artifacts.py:96`) is deliberate protocol conformity. `_prefix` normalizes
trailing slashes; `_scan_unload_location` clamps paren depth at 0. The
`catalog` param + `names[-2:]` drop are honest under the single-catalog
deployment — a signature-lie nit either way (G-288).

## Gaps promoted

| Gap ID | Severity | One-line |
|---|---|---|
| G-277 | S1 | `_external_location` regex scans literal-keeping SQL — a double-quoted identifier carrying `external_location = 's3://evil/'` shadows the real WITH property (valid SQL) so the manifest enumerates a foreign prefix's files; an escaped-quote literal yields `''` → FAILED on valid SQL (G-261/G-264 class, third site) |
| G-278 | S1 | INSERT/UNLOAD manifests cross-list concurrent writers — the before/after diff claims every key appearing under the target prefix in the window; probe: A's manifest contains B's `b.parquet`, violating the module's own "exactly the files a query wrote" contract |
| G-279 | S1 | `POST /v1/statement` retried on 429/502/503/504/empty-200 — one `submit_statement` issues 2 POSTs; a 502-after-accept double-executes INSERT/CTAS/UNLOAD server-side (upstream clients never retry submission) |
| G-280 | S3 | `GetQueryResults` NextToken `int()` leniency — `+3`/` 3 `/`03` decode to offset 3 → 200 where real Athena rejects malformed tokens (G-248 class, second site) |
| G-281 | S3 | `_split_s3_path` scheme-blind — `ftp://host/x`→`('ftp:','/host/x')`; non-`s3://` OutputLocations and UNLOAD `TO` targets accepted at submit, fail late at artifact write/snapshot where Athena 400s up front |
| G-282 | S3 | `S3WriterError` escapes `capture()` unshaped — `submission.py:410-415` catches only `ManifestTargetError`, so a `NoSuchBucket` listing failure is a submit-time 500 instead of the designed `manifest_target_error` degradation (write-time wraps correctly to `ArtifactWriteError`) |
| G-283 | S3 | Malformed-page member leniency + ragged-DESCRIBE crash — `nextUri:42`→`finished=True` silent truncation, non-list rows/non-dict columns dropped, `error:"str"` swallowed; `_describe_shape` `row[3]` `IndexError` kills the runner and parks the record RUNNING forever (log-only reap) |
| G-284 | S2 | Sync boto3 I/O inside async paths — measured 52.4 ms `capture` with **0 event-loop ticks**; 3 concurrent 50 ms-latency captures serialize at 154 ms; every moto roundtrip stalls all in-flight requests |
| G-285 | S2 | Retained `OutputSnapshot.before_paths` unbounded per record — +197 MB @ 2000×1000-key snapshots (103 B/key), +826 MB @ 1000×5000-key; 10k-cap × 1000-key ≈ 1 GB for data dead after the write |
| G-286 | S3 | Boundary error-absorption holes — non-ASCII `QueryExecutionContext.Database` → `UnicodeEncodeError` escapes `_send` (not `TransportError`) → unshaped submit 500; malformed Glue `Expression` (`'('`) → `re.error` past boto-only catches → 500 where Glue 400s |
| G-287 | S4 | Guard-arm test depth — 19/673 stmts uncovered (all error/guard arms), `GetQueryRuntimeStatistics` has no live-stack/bdd surface, and mutants M-6 (`<=0` token bound) + M-10 (`_to_clause_at` word-boundary, sits on uncovered `output_targets.py:263`) survive the full suite |
| G-288 | S3 | Declared-but-unread boundary parameters — `OutputSnapshotter.capture.catalog` (`output_targets.py:68`) and `get_query_results.store` (`query_results.py:33`) accepted and never consulted; `_qualified_name`'s `names[-2:]` silently drops `catalog.db.t`'s catalog segment |
| G-289 | S3 | Verbatim helper duplication — `_error_code`/`_objects`/`_string` identical across `glue_proxy.py:257-279,332-334` and `s3_writer.py:163-190` (24 lines); both boundaries also own parallel `_run` wrappers |
| G-290 | S3 | Cell-serialization parity — CSV artifact writes `"True"`/`"False"` where the wire emits `"true"`/`"false"` for the same record (`artifacts.py:198` `str(value)` vs `query_results.py:177-179`); complex cells render Python repr `{'k': 1}`/`[1, 2]` on both surfaces where Athena emits JSON |
