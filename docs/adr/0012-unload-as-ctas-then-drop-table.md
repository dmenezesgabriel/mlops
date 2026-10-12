# ADR-0012 — UNLOAD rewritten to a CTAS, then its Glue table is dropped

- Status: Accepted
- Date: 2026-09-26

## Context

Athena's `UNLOAD (query) TO 's3://…' WITH (props)` writes a query's results
to an S3 location without registering a catalog table. awswrangler emits it
for `read_sql_query(unload_approach=True)` and `wr.athena.unload()`
(`awswrangler/athena/_read.py:783-791`), then reads the result through
`Statistics.DataManifestLocation` like a CTAS result. Trino 483 has no
`UNLOAD` statement — the grammar rejects it outright (measured: 400
`InvalidRequestException`, surfaced by wrangler as `InvalidArgumentValue`).

Facts probed live on the running coordinator before deciding:

- `system.metadata.table_properties` for the `hive` catalog lists
  `format`, `external_location`, `partitioned_by`,
  `textfile_field_separator`, `csv_separator`, `null_format`,
  `transactional` — **no** compression property exists on a CTAS.
- `system.metadata.session_properties` lists `hive.compression_codec`
  (`NONE`/`SNAPPY`/`LZ4`/`ZSTD`/`GZIP`) — the only write-compression lever,
  carried on the submit POST by the client protocol's `X-Trino-Session`
  header.
- The moto Glue catalog holds no `default` schema, so a CTAS needs a
  schema-qualified name — only the request `Database` context can supply it.
- moto's Glue `delete_table` is a catalog-only operation (it cannot delete
  S3 objects), unlike Trino `DROP TABLE`, whose file behavior depends on
  the table's externality. Deleting the temp table via Glue therefore can
  never remove the files UNLOAD must leave behind.

## Decision

1. `dialect.unload_trino_submission` rewrites a statement-leading
   `UNLOAD (q) TO 'loc' WITH (props)` into
   `CREATE TABLE "<Database>"."athena_unload_<hex>" WITH
   (format=…, external_location=…, partitioned_by=…,
   textfile_field_separator=…) AS <q>`. The execution record keeps the
   Athena text and the `DML`/`UNLOAD` classification (same discipline as
   the earlier dialect entries, §11).
2. `compression='<name>'` maps to the `hive.compression_codec` session
   property sent as `X-Trino-Session` on the submit POST; Athena's `'zlib'`
   has no Trino codec and is rejected. An unknown `WITH` key or a missing
   `format` also fails the submission with `InvalidRequestException` — real
   Athena validates UNLOAD properties at submit too. With no `Database`
   context to host the temp table, the statement is left for Trino to
   reject rather than guessed at.
3. The `TO` path is snapshotted from the **original** statement text before
   the rewrite, because the rewrite consumes the clause the manifest
   resolver parses; the `{QueryID}-manifest.csv` diff keeps naming exactly
   the files the query wrote.
4. The generated Glue table is deleted through `GlueProxy` when the
   statement ends: strictly before `SUCCEEDED` (a cleanup failure reports
   `FAILED`, since a succeeded UNLOAD must leave no catalog residue — the
   same success-discipline as ADR-0009 #4's writer-before-transition), and
   best-effort on `FAILED`/`CANCELLED`, where the record already carries
   the truer reason.
5. Semantic delta, documented rather than hidden: real UNLOAD registers no
   table; the emulator briefly registers one for the statement's lifetime
   — invisible to consumers once the execution is terminal. UNLOAD into a
   non-empty `TO` location fails with the engine's
   `HIVE_PATH_ALREADY_EXISTS`, matching real Athena's non-empty-target
   rejection, so callers must pass a fresh path.

## Consequences

- `read_sql_query(unload_approach=True)` and `wr.athena.unload()` run
  unmodified: the manifest → parquet read path is identical to the CTAS
  approach wrangler already uses (nb04 PARITY rows PASS).
- `field_delimiter` maps to `textfile_field_separator`, the probed property
  for TEXTFILE writes; it is inert for columnar formats, as in Athena.
- `partitioned_by` passes through verbatim (same `ARRAY[…]` expression in
  both dialects) and Trino writes the `key=value/` directories consumers
  list.
- A consumer polling Glue mid-execution can observe the `athena_unload_*`
  table until the terminal cleanup removes it — the bounded, documented
  price of riding the engine's real writer instead of fabricating files.
