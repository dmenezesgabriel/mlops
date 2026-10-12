# Gap register — Athena Local Emulator (EPHEMERAL)

> **EPHEMERAL WORK REGISTER — iterates freely; never cited from code.**
> Consolidates the measured `FAIL`/`GAP` rows the parity notebooks record in
> `projects/athena_emulator/PARITY.md`. One row per measured gap: the wire
> evidence, the expected AWS behavior, and a candidate fix surface so each
> fix lands as a small step. NB-6 triage promotes rows to backlog items;
> NB-5 may append more rows. A row leaves the register when its fix ships
> (PARITY.md flips to PASS) or is waived with a documented reason.

| ID | Feature (PARITY.md row) | Measured on the wire | Expected AWS behavior | Candidate fix surface | Size |
|---|---|---|---|---|---|

Every measured row has shipped or been waived — the register is empty; the
closed dispositions live in §Triage below.

## Triage (NB-6, 2026-09-25)

Every register row is promoted to a backlog fix item (`GF-*`, section J of
`backlog.md`) or waived with a documented reason. Rows stay until their fix
ships (PARITY.md flips to PASS); waived rows are closed evidence — a scoped
boundary decision, not a defect.

| Row | Disposition | Item | Reason / note |
|---|---|---|---|
| GP-1 | shipped | GF-1 | `WorkGroup.State` gate at submit; extended to `CreateNamedQuery`/`CreatePreparedStatement` (AWS UG: disabled workgroups also block new named queries) |
| GP-2 | shipped | GF-2 | `WorkGroupStore.list` gained the sibling stores' opaque-offset paging; `MaxResults` bounded to the model's `MaxWorkGroupsCount` 1..50 |
| GP-3 | shipped | GF-3 | Terminal early-return in `QueryExecutor.cancel` before the transition and the Trino DELETE — the canonical model marks the op idempotent |
| GP-4 | shipped | GF-4 | `ExecutionStore.by_request_token` (workgroup, token) → execution-id map; `QueryExecutor.start` replays identical submissions, drifted params → `InvalidRequestException` 400 |
| GP-5 | shipped | GF-5 | `find_reusable` matches the AWS UG conditions newest-first; `reuse_results_from` re-answers the source's OutputLocation + cached rows with no Trino round-trip |
| GP-6 | shipped | GF-6 | `ensure_executable_catalog` (data_catalog_state.py) gates the start path after context parse — unregistered names answer the store's "does not exist" 400, and registered non-GLUE catalogs reject too ("only GLUE catalogs execute queries") since the single query plane is the Glue-backed Trino catalog |
| GP-7 | shipped | GF-7 | One shared dialect rule covers GP-7+GP-8 |
| GP-8 | shipped | GF-7 | Shares GF-7 |
| GP-9 | shipped | GF-8 | `system.sync_partition_metadata` is the Trino-native MSCK equivalent — probed signature: `case_sensitive` is BOOLEAN default `true` (Hive-compatible), so the 3-arg `ADD` form is emitted |
| GP-10 | shipped | GF-9 | `unload_trino_submission` rewrites to a CTAS at the `TO` path (compression → `hive.compression_codec` session property); the generated Glue table is dropped at completion — strict before SUCCEEDED, best-effort otherwise (ADR-0012) |
| GP-11 | shipped | GF-9 | Shares GF-9 |
| GP-12 | shipped | GF-10 | Probed the coordinator at fix time: Trino 483's SHOW grammar has no PARTITIONS form at all (every FROM/IN spelling fails `mismatched input 'PARTITIONS'` at 1:6) — mapped to `SELECT * FROM "<schema>"."<t>$partitions"`; wire rows are columnar where real Athena renders `key=value` (accepted shape-vs-content delta; AWS's own docs name `$partitions` the listing equivalent) |
| GP-13 | shipped | GF-11 | `CREATE EXTERNAL TABLE … STORED AS … LOCATION` → `CREATE TABLE … WITH(external_location, format, partitioned_by)` |
| GP-14 | shipped | GF-12 | Probed signature corrected the sketch: `register_partition(schema, table, partition_columns ARRAY, partition_values ARRAY, location)` — 5 args with `location` optional (4-arg form covers the omitted-LOCATION default); the procedure is disabled by default → `hive.allow-register-partition-procedure=true` in `docker/trino/catalog/hive.properties`. `IF NOT EXISTS` rides the record: Trino's `ALREADY_EXISTS` fires before any mutation → succeeded as AWS's no-op. Accepted deltas: spec keys emit in statement order, and Trino requires the location dir to exist where AWS registers empty prefixes |
| GP-15 | shipped | GF-13 | Un-waived and shipped 2026-09-26: dedicated `iceberg` Trino catalog on the same moto Glue + `iceberg_table.py` maps `TBLPROPERTIES('table_type'='ICEBERG')` CREATE (backticks normalized; `bucket(N,col)` re-ordered to Trino's `(col,N)`); `iceberg.py` routes `INSERT`/`MERGE`/`SELECT` references on the Glue `table_type` marker so wrangler's staged hive temp tables stay session-catalog; `iceberg.field.current` column markers injected by the moto overlay (wrangler's `filter_iceberg_current`). Accepted deltas: `write_compression`/optimize/vacuum hints dropped, multi-column `ADD COLUMNS` + `CHANGE COLUMN` renames reject. ADR-0013 |
| GP-16 | shipped | GF-13 | Shares GF-13 — `MERGE INTO … WHEN MATCHED THEN DELETE` qualifies only the Iceberg target; live wrangler probe deletes the matched row |
