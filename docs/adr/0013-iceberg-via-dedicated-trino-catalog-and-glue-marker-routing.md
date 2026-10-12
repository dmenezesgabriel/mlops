# ADR-0013 — Iceberg through a dedicated Trino catalog, routed on the Glue `table_type` marker

- Status: Accepted
- Date: 2026-09-26

## Context

`wr.athena.to_iceberg` and `wr.athena.delete_from_iceberg_table` drive
three shapes over the wire (awswrangler/athena/_write_iceberg.py): a
`CREATE TABLE … TBLPROPERTIES('table_type'='ICEBERG')` DDL, a staged
`INSERT INTO … SELECT` / `MERGE INTO … WHEN MATCHED THEN DELETE` DML, and
Hive-flavored `ALTER TABLE … ADD COLUMNS` / `CHANGE COLUMN` schema
evolution. Two hard blockers measured on the live stack:

- `docker/trino/catalog/` carried only the `hive` connector — it answers
  any statement touching an Iceberg table with
  `UNSUPPORTED_TABLE_TYPE [EXTERNAL]` (probed on the coordinator), so
  nothing Iceberg can run through the session catalog.
- The Iceberg connector needs its own Glue-backed catalog, and the
  submitted statement must say *which* catalog each table lives in — the
  Trino session catalog is fixed at submit and cannot differ per table.

Facts probed live before deciding:

- `trinodb/trino:483` ships the `iceberg` plugin;
  `iceberg.catalog.type=glue` + the shared `hive.metastore.glue.*`
  properties + the same moto S3 block make a second catalog register
  Iceberg tables in the same moto Glue with
  `Parameters.table_type=ICEBERG`, `metadata_location`, and
  `StorageDescriptor.Location` — exactly the metadata AWS's Iceberg Glue
  integrations record.
- `CREATE`/`INSERT`/`SELECT`/`MERGE`/`DELETE` all work against moto Glue
  without overlay changes; cross-catalog `INSERT INTO iceberg … SELECT
  FROM hive` works, which is precisely wrangler's staging shape.
- Athena writes `bucket(N, col)`/`truncate(N, col)` partition transforms;
  Trino's `partitioning=ARRAY[…]` strings take `(col, N)` — the
  coordinator rejects Athena's order with `INVALID_TABLE_PROPERTY`.
- `SHOW SESSION` on the iceberg catalog lists no write-compression
  property — Athena's `write_compression` and the `optimize_*`/`vacuum_*`
  hints have no Trino counterpart and are dropped, matching AWS's
  engine-side-hint semantics.
- Trino allows one action per `ALTER TABLE`, so AWS-valid multi-column
  `ADD COLUMNS (a, b)` and rename-in-`CHANGE COLUMN` cannot be single
  statements — they are rejected at submit with the same class of
  `InvalidRequestException` real Athena answers for unsupported forms.
- wrangler's `get_table_types(filter_iceberg_current=True)` filters Glue
  columns on `Parameters['iceberg.field.current']`, a marker real
  Athena's Iceberg engine writes at registration; Trino does not write
  it, so the moto overlay injects it on `create_table`/`update_table`
  (docker/moto/glue_overlay.py) — without it a second `to_iceberg` call
  reads an empty schema and rejects its own frame.

## Decision

1. `docker/trino/catalog/iceberg.properties` — a second Trino catalog
   named `iceberg` over the same moto Glue + S3, `iceberg.format-version=2`
   pinned (Athena creates Iceberg v2 tables; Trino defaults to 2 anyway).
2. `iceberg_table.py` maps the DDL:
   `TBLPROPERTIES('table_type'='ICEBERG')` CREATE →
   `CREATE TABLE iceberg."db"."t" … WITH(format, location[, partitioning])`
   with hive types translated and transforms re-ordered; routed ALTERs
   convert `ADD COLUMNS` → `ADD COLUMN` and `CHANGE COLUMN` →
   `ALTER COLUMN … SET DATA TYPE`. `format` values outside
   parquet/orc/avro, unknown TBLPROPERTIES keys, a missing `LOCATION`,
   multi-column adds, and renames raise `InvalidRequestException` at
   submit — mirroring AWS's submit-time validation ("only a predefined
   list").
3. `iceberg.py` routes everything else by *reference scan*, not catalog
   switching: anchors (`insert into`, `merge into`, `delete from`,
   `alter/drop/truncate table`, `describe`, `show create table`,
   `update`, `from`, `join`, `using`) get their table reference qualified
   `iceberg."schema"."table"` when a `GlueIcebergProbe` read of moto
   Glue's `Parameters.table_type` says Iceberg. Hive-bound references
   (staging temp tables) stay unqualified and resolve in the session's
   hive catalog — the cross-catalog statement Trino executes is exactly
   the shape wrangler intends.
4. The routing path normalizes `` `ident` `` → `"ident"` first: Athena's
   DDL engine accepts backticks (wrangler emits them); Trino's parser
   rejects them outright.
5. `QueryExecutor` runs the routing in the dialect slot — before
   `to_trino_dialect`, after UNLOAD/ADD-PARTITION (those statements
   cannot be Iceberg) — and keeps the Athena text on the wire record, the
   same discipline as every earlier dialect entry.

## Consequences

- `SELECT`/DML over Iceberg tables route per-statement on a Glue read;
  CTEs and table functions are unaffected (the probe answers False).
- Accepted deltas, all documented in code: `write_compression` and the
  optimize/vacuum hints are dropped; multi-column `ADD COLUMNS` and
  `CHANGE COLUMN` renames reject; `MSCK`/`SHOW PARTITIONS`/`SHOW CREATE
  TABLE` on Iceberg tables keep the hive-path behavior of real Athena's
  Iceberg surface being narrower than its Hive surface.
- The routing probe shares `GlueProxy` with the manifest snapshotter —
  the same moto read answers both questions, one Glue boundary
  (architecture §5).
