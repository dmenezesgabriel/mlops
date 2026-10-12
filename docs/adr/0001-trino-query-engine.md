# ADR-0001 — Trino is the SQL engine, driven via `/v1/statement`

- Status: Accepted
- Date: 2026-09-19
- Applies to: `athena-local` query execution

## Context

The emulator must execute SQL (`SELECT`, DDL, CTAS, partitioned reads). moto's
Athena does not execute queries; its docs state: "Queries are not executed by
Moto, so [StartQueryExecution] will always return 0 rows by default"
(`research_repos/moto/docs/docs/services/athena.rst:48`). moto's Athena backend
is metadata-only: `start_query_execution` at
`research_repos/moto/moto/athena/models.py:314`, DDL handled by a regex
`_process_ddl` at `:345`, results faked via `_store_query_result_in_s3` at
`:475` (a canned CSV from moto-api `/moto-api/static/athena/query-results`).

LocalStack — the validated real-world reference for wrangler/pyathena — also
routes Athena through Trino for federated/engine work (docs.localstack.cloud,
aws/services/athena).

Trino exposes a stateless statement protocol: `POST /v1/statement`, poll
`GET nextUri`, `DELETE` to cancel; headers `X-Trino-User` (required),
`X-Trino-Catalog`, `X-Trino-Schema`; response carries `columns`/`data`/
`stats`/`error`/`updateType` (trino.io — `develop/client-protocol.html`).

## Decision

Athena-local executes every query through Apache Trino:

- Emulator `POST`s the query to Trino with `X-Trino-Catalog: hive`,
  `X-Trino-Schema: <database>`, `X-Trino-User: <AWS principal>`.
- It polls `nextUri` until a final result or `error`; `StopQueryExecution`
  maps to a `DELETE` of the statement.
- All Trino access is wrapped in the project-owned `trino_client.py` thin
  interface (per `AGENTS.md` dependency rule) so no handler depends on Trino
  types directly.

Hive connector parameters (TRINO metastore + S3 docs): catalog mounted with
`hive.metastore=glue` + `hive.metastore.glue.endpoint-url/region/aws-access-key/
aws-secret-key` (trino.io `object-storage/metastores.html`) and native S3
(`fs.s3.enabled=true`, `s3.endpoint`, `s3.path-style-access=true`) — see
ADR-0005 and ADR-0006.

## Consequences

- Real SQL semantics (joins, aggregations, partitioned reads) come from Trino,
  not from us.
- Two containers are required (`trino` + `athena`), wired in compose
  (ADR-0002).
- Trino errors must be mapped to Athena-shaped exceptions (ADR-0008).
- moto's `_process_ddl` regex path (`models.py:345`) is bypassed entirely: DDL
  lands in moto Glue through Trino's Hive connector (ADR-0005).