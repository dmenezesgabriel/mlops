# PRD — Athena Local Emulator (EPHEMERAL)

> **EPHEMERAL PRODUCT REQUIREMENT DOCUMENT — working document.**
> It will drift. Do **not** quote PRD content, IDs, or wording in code,
> docstrings, or comments. Code comments may reference only the permanent
> docs (`docs/athena-emulator/architecture.md`, `docs/athena-emulator/adr/*`).
> Requirements below carry evidence anchors; implementers must check those
> anchors, not this prose.

## 1. Goals

A local Athena emulator (lib `athena-local`) that executes SQL via Trino and
serves the Athena 2017-05-18 JSON 1.1 protocol so the following run unmodified
against `http://localhost:5001`:

- boto3 consumers (`research_repos/boto3`, botocore) with
  `AWS_ENDPOINT_URL_ATHENA` / `endpoint_url`
- awswrangler (`research_repos/aws-sdk-pandas`) via `athena_endpoint_url`
  (`awswrangler/_utils.py:255-280`, `:259-260`)
- AWS CLI `athena` commands (`research_repos/aws-cli/awscli/examples/athena/`)
- terraform-provider-aws `aws_athena_*` (SDK Go v2 custom endpoints:
  `AWS_ENDPOINT_URL_ATHENA`)
- alongside moto S3/Glue already in this repo's `docker-compose.yml` on
  `mlops_net`

## 2. Non-goals (v1)

- Athena Studio / notebook / session / calculation / capacity APIs (ADR-0004).
- Persistent state beyond in-memory registries (ADR-0003).
- Multiple replicas, HA, multi-node Trino.
- Production-grade authN/authZ (static test creds; Athena's auth is out of
  scope for a local emulator).

## 3. Protocol contract (all FRs rest on this)

JSON 1.1, 70 ops, `POST /`, header `X-Amz-Target: AmazonAthena.<Op>` (dispatch on the segment after the final dot) —
canonical model `research_repos/aws-cli/awscli/botocore/data/athena/2017-05-18/service-2.json`.
Errors: `{"__type": "<ExceptionShape>", "message": "..."}` + `X-Amzn-Errortype`
header, status from model `httpStatusCode` (ADR-0008). moto reference:
`research_repos/moto/moto/core/serialize.py:492,538`,
`research_repos/moto/moto/core/exceptions.py:100`.

## 4. Functional requirements

| ID | FR | Evidence (research_repos/…) | Acceptance |
|---|---|---|---|
| FR-01 | `StartQueryExecution` honors `QueryString`, `QueryExecutionContext.{Database,Catalog}`, `ResultConfiguration.OutputLocation`, `WorkGroup`, `ExecutionParameters`; returns `QueryExecutionId` (UUID) | `awswrangler/athena/_utils.py:89-155` builds exactly these args; model `StartQueryExecutionRequest` | Wrangler `read_sql_query` runs; CLI `start-query-execution` example works |
| FR-02 | `GetQueryExecution` / `BatchGetQueryExecution` return full `QueryExecution` incl. `Status`, `Statistics.{DataScannedInBytes,EngineExecutionTimeInMillis,DataManifestLocation}`, `StatementType`, `OutputLocation` (artifact path per ADR-0007) | `awswrangler/athena/_cache.py:36-45` (cache reads batch); `_utils.py:41-42` (terminal states) | Wrangler cache + `read_sql_query` poll succeed |
| FR-03 | `GetQueryResults`: `Rows[0]` = header; cells `{"VarCharValue": "<str>"}`; `MaxResults` ≤ 1000 + opaque `NextToken`; terminal-only (400 pre-finish per ADR-0008/0009) | `awswrangler/athena/_read.py:335-384` (`page_rows[1:]` `:357,:383`); model `GetQueryResultsOutput` | Wrangler `read_sql_query` inline path returns data |
| FR-04 | DML `SELECT` writes `{QueryID}.csv` (headerless, QUOTE_ALL) + `.csv.metadata` to moto S3 before SUCCEEDED | `awswrangler/athena/_read.py:209-238`; AWS docs querying-finding-output-files | Wrangler `s3.read_csv` path + file cleanup works |
| FR-05 | `UTILITY` (`DESCRIBE`, `SHOW CREATE TABLE`) writes `{QueryID}.txt` (tab, QUOTE_ALL) + `.txt.metadata` | `awswrangler/athena/_utils.py:190-221`; `StatementType` enum | `athena_utils` show-create-table works via wrangler |
| FR-06 | CTAS (`CREATE TABLE … WITH(…) AS SELECT`) selects into moto S3 via Trino, writes `{QueryID}-manifest.csv` + `{QueryID}.metadata`, sets `Statistics.DataManifestLocation` | `awswrangler/athena/_utils.py:860-872,888-898`; `_read.py:62-81,135-206` (`metadata` path via `.replace` `:153`) | `wr.read_sql_query(ctas_approach=True)` then read parquet from manifest works |
| FR-07 | Partitioned reads: `SELECT` from a table with Hive partitions (`external_location` + `partitioned_by`) | ADR-0006 spike + Trino Hive connector; moto Glue partitions | `SHOW PARTITIONS` / partitioned `SELECT` via wrangler |
| FR-08 | `ListDatabases` / `GetDatabase` / `ListTableMetadata` / `GetTableMetadata` served from moto Glue (proxy), consistent with engine view | ADR-0005; `research_repos/moto/moto/glue/models.py:360` | CLI `list-table-metadata` example works and matches Trino view |
| FR-09 | Workgroups: `CreateWorkGroup` (409/400 on duplicate per moto `responses.py:26`), `GetWorkGroup`, `ListWorkGroups`, `UpdateWorkGroup`, `DeleteWorkGroup`; moto-like default `primary` | `research_repos/moto/docs/docs/services/athena.rst`; `awswrangler/athena/_utils.py:158-187` (`GetWorkGroup` + `EnforceWorkGroupConfiguration`) | Wrangler runs with no explicit workgroup (default `primary`); CLI `list-work-groups` |
| FR-10 | `CreateNamedQuery` / `GetNamedQuery` / `ListNamedQueries` / `DeleteNamedQuery` / `BatchGetNamedQuery` | moto coverage `athena.rst`; CLI `create-named-query.rst` | CLI named query flow passes |
| FR-11 | Prepared statements: `Create/Get/List/Update/DeletePreparedStatement` + `BatchGetPreparedStatement`; get on missing → `ResourceNotFoundException` | `awswrangler/athena/_statements.py:26-29` (expects RNFE); CLI `create-prepared-statement.rst` | `wr.athena.read_sql_query(ctas_approach=True)` with prepared statement path; CLI |
| FR-12 | Data catalogs: `Create/Get/List/Update/DeleteDataCatalog` (`GLUE`/`HIVE`/`LAMBDA` types per model) | model `DataCatalog`/`DataCatalogType` | CLI `create-data-catalog.rst`; Go SDK parity test |
| FR-13 | `ListEngineVersions` returns pinned list (wrangler/CLI probe) | ADR-0004 | CLI `list-engine-versions.rst` |
| FR-14 | `StopQueryExecution` → Trino cancel → `CANCELLED` (ADR-0009) | trino.io client-protocol (`DELETE`); model `QueryExecutionState` | CLI `stop-query-execution.rst`; `GetQueryExecution` shows CANCELLED |
| FR-15 | `GetQueryRuntimeStatistics` returns recorded counters | ADR-0009; model output | CLI `get-query-runtime-statistics.rst` |
| FR-16 | `TagResource`/`UntagResource`/`ListTagsForResource` for executions/resources | moto implementations (models.py) | CLI/boto3 tag round-trip |
| FR-17 | Out-of-scope Studio/session/calculation/capacity ops → shaped `InvalidRequestException` 400 (ADR-0004) | ADR-0004; model op list | Negative test: each op errors, botocore parses error cleanly |
| FR-18 | SQL-error mapping: Trino parse/analysis errors become Athena `InvalidRequestException` 400 with messages wrangler recognizes (`"Exception parsing query"`, `"extraneous input"`-compatible) | `awswrangler/athena/_utils.py:888-898` | `wr.read_sql_query` with bad SQL raises `InvalidCtasApproachQuery`/ClientError as expected |
| FR-19 | Endpoint wiring: honor `AWS_ENDPOINT_URL_ATHENA`, `athena_endpoint_url`, CLI `--endpoint-url`, TF env — only for Athena traffic (ADR-0002) | `awswrangler/_utils.py:255-280`; botocore models; TF custom endpoints guide | Each consumer reaches `:5001` for Athena, moto `:5000` for S3/Glue |

## 5. Non-functional requirements (NFR)

| ID | NFR | Enforcement |
|---|---|---|
| NFR-01 | TDD: every source change starts with a failing test; regression tests for bug fixes; tests F.I.R.S.T. | `make test`, backlog QC items |
| NFR-02 | Toolchain gates green at every commit: pytest, pytest-cov, pytest-bdd, pyright, ruff, bandit, vulture, xenon, radon, semgrep, import-linter, deptry | pre-commit + per-lib `make quality` (architecture §8.4, backlog QC-*) |
| NFR-03 | Typed: pyright standard, no `any`/`Dict`, explicit types on every public function | `make type-check` |
| NFR-04 | No moto internals reuse (own dispatch/errors) | architecture §4, ADR-0008 |
| NFR-05 | Style: files < 500 lines; functions 4–20 lines; ruff default; radon cc < C; xenon MI threshold; vulture no dead code | `make complexity`, QC items |
| NFR-06 | Structured JSON logging (observability); plain text only for CLI-facing output | architecture §8.3 |
| NFR-07 | Dependency hygiene: deptry clean; third-party wrapped behind project-owned interfaces | root `make dependencies`; AGENTS.md deps rule |
| NFR-08 | Import contract: import-linter contracts declared at root (lib boundary: nothing inside `athena_local` may import `libs/*` other than its declared deps) | `uv run lint-imports` |
| NFR-09 | Compose: works on `mlops_net` with existing moto (port 5000) and jupyterlab services; no client changes needed | `docker compose up`, consumer test suites |
| NFR-10 | Performance sanity: moderately sized SELECT returns via wrangler poll loop (1 s cadence) without timeouts | consumer suite timing assertion (no hard SLA v1) |

## 6. Out of scope (v1) — reference only (ADR-0004)

Notebook/session/calculation ops, capacity reservations, executors, resource
dashboard, application DPU sizes, presigned notebook URLs. All respond with
shaped errors (FR-17).