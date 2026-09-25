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
| GP-2 | `list_work_groups` honors `MaxResults`/`NextToken` (nb02) | `MaxResults=1` returned all 6 workgroups, no `NextToken` | page the list like `ListNamedQueries`/`ListQueryExecutions` do | `workgroups.py` list handler: opaque-offset pagination (same pattern as query executions) | S |
| GP-3 | `StopQueryExecution` on a terminal execution (nb03, FAIL) | `InternalServerException` 500 on a SUCCEEDED execution | 200 no-op — stopping a finished execution is idempotent | `query_executions.py` stop handler: return 200 when state is terminal | S |
| GP-4 | `ClientRequestToken` dedupes retried submissions (nb03) | same token submitted twice → two distinct execution ids | a retried token returns the original `QueryExecutionId` | `executions.py` store: (workgroup, token) → execution-id map checked at submit | S–M |
| GP-5 | `ResultReuseConfiguration` reuses recent results (nb03) | accepted but never applied; no `Statistics.ResultReuseInformation`; second run re-executed | reuse a recent identical execution within `ResultReuseByAgeConfiguration.MaxAgeInMinutes`; report `ResultReuseInformation.ReusedPreviousResult` | `executions.py`/`query_executions.py`: reuse lookup keyed on query text + workgroup + age | M |
| GP-6 | unknown `Catalog` rejected at submit (nb03) | unregistered catalog accepted; executes on `hive` regardless | reject unregistered catalogs at submit | `data_catalog_state.py` + start path: validate `QueryExecutionContext.Catalog` against registered catalogs | S |
| GP-7 | `describe_table` column listing (nb04) | 400 `InvalidRequestException`: `backquoted identifiers are not supported` (wrangler sends `DESCRIBE \`t\`;`) | DESCRIBE returns the column listing | `dialect.py`: normalize backtick identifiers → double-quoted and strip the statement terminator for `DESCRIBE`/`SHOW CREATE TABLE` (shares fix with GP-8) | S |
| GP-8 | `show_create_table` statement (nb04) | 400 `InvalidRequestException`: `backquoted identifiers are not supported` | `SHOW CREATE TABLE` text returned | same dialect rule as GP-7 | S (with GP-7) |
| GP-9 | `repair_table` — `MSCK REPAIR TABLE` (nb04) | 400: `mismatched input 'MSCK'` | MSCK discovers unregistered partitions | `dialect.py`: map `MSCK REPAIR TABLE t` → Trino Hive `CALL system.sync_partition_metadata('schema','t','ADD','CASCADE')` (trino.io hive connector procedures) | M |
| GP-10 | `read_sql_query(unload_approach=True)` (nb04) | 400 `InvalidRequestException` on `UNLOAD`, surfaced as wrangler `InvalidArgumentValue` | UNLOAD writes query results to `TO` path in the requested format | no Trino `UNLOAD`; candidate dialect rewrite → CTAS with `external_location` + format props, or a documented waiver — needs an ADR note if rewritten | M–L |
| GP-11 | `wr.athena.unload()` (nb04) | 400 `InvalidRequestException` on `UNLOAD`, surfaced as wrangler `InvalidArgumentValue` | same as GP-10 | same decision as GP-10 | with GP-10 |
| GP-12 | `SHOW PARTITIONS <t>` Athena spelling (nb04) | 400: `mismatched input 'PARTITIONS'` — workaround `"t$partitions"` reads fine (PASS) | `SHOW PARTITIONS t` lists partition values | `dialect.py`: map `SHOW PARTITIONS t` → `SELECT * FROM "t$partitions"` (or `SHOW PARTITIONS FROM t` if Trino 483 accepts — verify against the coordinator at fix time) | S–M |
| GP-13 | `CREATE EXTERNAL TABLE` Athena spelling (nb05) | 400 `InvalidRequestException`: `line 1:8: mismatched input 'EXTERNAL'` | creates an external table over S3 | `dialect.py`: map `CREATE EXTERNAL TABLE … [PARTITIONED BY …] STORED AS … LOCATION …` → Trino `CREATE TABLE … WITH(external_location, format, partitioned_by)`; serde/`TBLPROPERTIES` pairs beyond format+location are unmappable — waiver candidate for those | M |
| GP-14 | `ALTER TABLE … ADD [IF NOT EXISTS] PARTITION` (nb05) | 400: `line 1:37: mismatched input 'IF'` on `ADD IF NOT EXISTS PARTITION (region='AP') LOCATION …` | registers the partition in the catalog | `dialect.py`: map to `CALL system.register_partition('schema','t',ARRAY[…],'location')` (trino.io hive procedures); `system.sync_partition_metadata` covers the already-on-S3 layout | M |
| GP-15 | `wr.athena.to_iceberg` (nb05) | 400: `backquoted identifiers are not supported` on `CREATE TABLE `t` (…) TBLPROPERTIES('table_type'='ICEBERG', 'format'='parquet')` | creates an Iceberg table, then `INSERT INTO … SELECT` | two blockers — dialect map (backticks/`TBLPROPERTIES`) AND no Iceberg connector provisioned (`docker/trino/catalog/`); fix = add an `iceberg` catalog on the same moto Glue + map the DDL, or waive as out of emulator scope | L / waiver |
| GP-16 | `wr.athena.delete_from_iceberg_table` (nb05) | never reached the wire — wrangler raises `InvalidTable` client-side because the target can't be created (GP-15) | deletes matching rows from an Iceberg table | gated by GP-15: with an Iceberg catalog the `DELETE FROM … WHERE EXISTS(…)` lands on Trino's iceberg connector (row delete supported); shares GP-15's fix-or-waive decision | with GP-15 |

## Triage (NB-6, 2026-09-25)

Every register row is promoted to a backlog fix item (`GF-*`, section J of
`backlog.md`) or waived with a documented reason. Rows stay until their fix
ships (PARITY.md flips to PASS); waived rows are closed evidence — a scoped
boundary decision, not a defect.

| Row | Disposition | Item | Reason / note |
|---|---|---|---|
| GP-1 | shipped | GF-1 | `WorkGroup.State` gate at submit; extended to `CreateNamedQuery`/`CreatePreparedStatement` (AWS UG: disabled workgroups also block new named queries) |
| GP-2 | fix | GF-2 | Same opaque-offset pagination `ListNamedQueries`/`ListQueryExecutions` already use |
| GP-3 | fix | GF-3 | Only measured FAIL — return 200 no-op when the execution is terminal |
| GP-4 | fix | GF-4 | (workgroup, token) → execution-id map in the store; real AWS dedupes retried tokens |
| GP-5 | fix | GF-5 | Server-side reuse is a documented AWS feature; keyed on query text + workgroup + `MaxAgeInMinutes` |
| GP-6 | fix | GF-6 | Validate `QueryExecutionContext.Catalog` against registered catalogs at submit |
| GP-7 | fix | GF-7 | One shared dialect rule covers GP-7+GP-8 |
| GP-8 | fix | GF-7 | Shares GF-7 |
| GP-9 | fix | GF-8 | `system.sync_partition_metadata` is the Trino-native MSCK equivalent |
| GP-10 | fix | GF-9 | Dialect rewrite to CTAS-at-`TO`-path + catalog drop; needs an ADR note (semantic delta: real UNLOAD registers nothing) |
| GP-11 | fix | GF-9 | Shares GF-9 |
| GP-12 | fix | GF-10 | Map to `"t$partitions"` or Trino's native spelling — verify against the coordinator at fix time |
| GP-13 | fix | GF-11 | `CREATE EXTERNAL TABLE … STORED AS … LOCATION` → `CREATE TABLE … WITH(external_location, format, partitioned_by)` |
| GP-14 | fix | GF-12 | `ALTER TABLE … ADD PARTITION` → `CALL system.register_partition` |
| GP-15 | waived | — | Iceberg writes need a dedicated `iceberg` Trino catalog on moto Glue **and** an Athena-DDL dialect map (`TBLPROPERTIES`, backticks) — a connector-level capability the PRD never scoped (FR-01…20 list no Iceberg). Revisit if a consumer needs it |
| GP-16 | waived | — | Gated by GP-15 — shares the Iceberg scope decision |
