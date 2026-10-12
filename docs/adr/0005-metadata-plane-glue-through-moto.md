# ADR-0005 — Catalog metadata through moto Glue (Hive metastore=glue + read proxy)

- Status: Accepted
- Date: 2026-09-19

## Context

Trino's Hive connector needs a metastore. moto emulates the Glue Data Catalog
(<stub> full database + table + partition surface (create/get/delete database,
table, partition versions in `research_repos/moto/moto/glue/responses.py`;
`get_databases` at `research_repos/moto/moto/glue/models.py:360`,
`batch_get_partition` at `:1240`)). Trino ships a native Glue metastore:
`hive.metastore=glue` with `hive.metastore.glue.endpoint-url`,
`hive.metastore.glue.region`, `hive.metastore.glue.aws-access-key`,
`hive.metastore.glue.aws-secret-key` (trino.io — `object-storage/metastores.html`).

Athena's API also exposes catalog introspection (`GetDatabase`, `ListDatabases`,
`GetTableMetadata`, `ListTableMetadata`, `GetDataCatalog`, `ListDataCatalogs`)
whose answers must agree with what Trino actually sees — single source of
truth means both paths read the same store.

## Decision

- The `hive` catalog in Trino is configured `hive.metastore=glue` with
  endpoint `http://moto:5000`, region `us-east-1`, static creds
  `test`/`test`; DDL from queries flows Trino → moto Glue.
- Athena catalog-read operations (`list_databases`, `get_database`,
  `list_table_metadata`, `get_table_metadata`) are implemented by
  `glue_proxy.py` as a thin boto3 client proxying to the same moto Glue — so
  API answers and engine views cannot diverge.
- `data_catalog`/`workgroup`/etc. remain emulator-owned (ADR-0003).

## Consequences

- One catalog store; DDL visible to both engine and API with no sync code.
- Requires moto to keep Glue on `:5000` and be reachable from both `trino`
  and `athena` containers.
- Risk: Trino's Glue metastore may issue `GetUserDefinedFunctions`, which moto
  Glue does not implement — spike item (see milestones M0, architecture §11):
  verify with `SHOW FUNCTIONS` + a DDL round-trip before integrating.