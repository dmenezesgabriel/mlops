# Athena Local Emulator — Architecture (arc42)

Applies to `libs/athena-local` and the `athena` + `trino` docker services.
Permanent reference — code comments may cite this file and `/adr/`. Sections
follow arc42 (https://arc42.org/documentation/).

## 1. Introduction and Goals

### 1.1 Requirements overview
A local AWS Athena substitute that *executes SQL* and produces the exact
artifacts and API responses that real Athena does — so that the five target
consumers pass unmodified:

1. **boto3 / botocore** — `endpoint_url` / `AWS_ENDPOINT_URL_ATHENA`
2. **awswrangler** (aws-sdk-pandas) — `athena.read_sql_query`, `to_parquet`,
   cache, CTAS
3. **AWS CLI** (`athena` commands)
4. **terraform** via hashicorp/terraform-provider-aws (`aws_athena_*` resources)
5. **moto**-emulated S3 + Glue (already in this repo's `docker-compose.yml`)

### 1.2 Quality goals (see §10)
| Goal | Measure |
|---|---|
| Wire-parity | Every response/error parses with unmodified botocore/stubs |
| Consumer-parity | The 5 consumers above work without config hacks |
| Typed code | pyright standard, no `any`, no `Dict` |
| Evidence-driven | Every behavior traces to a `research_repos/` anchor |
| TDD | Every change: red → green → refactor; gates at every commit |

## 2. Constraints

- Language/deps: Python ≥ 3.11, uv workspace, httptastic layout like
  `libs/sagemaker-local` (src layout, pyproject, Makefile, docker/, tests/).
- Dijkstra-style rule from `AGENTS.md`: max 2 indent levels, no `else`,
  4–20-line functions, files < 500 lines.
- Compose network `mlops_net` (existing `docker-compose.yml`); moto stays on
  its own port serving S3/Glue/STS.
- `research_repos/` checkouts are frozen references — never edited by the
  implementation.
- Trino officially tests only real AWS S3 and MinIO; the moto S3 link was
  spike-proven end-to-end before integration (ADR-0006). Remaining moto Glue
  gaps are bridged by the repo-owned overlay in `docker/moto/` (§7, §11).

## 3. Context and Scope

### 3.1 System context
```
        boto3 / awswrangler / AWS CLI / terraform-provider-aws
                     │  AWS_ATHENA endpoint (5001)
                     ▼
              ┌─────────────┐      Trino /v1/statement      ┌───────────────┐
              │  athena-local│ ────────────────────────────► │     trino     │
              │  (FastAPI)   │ ◄──────────────────────────── │  (Hive conn.) │
              └──────┬──────┘                                └───────┬───────┘
                     │ boto3 proxy (catalog/,artifact writes)        │
                     ▼                                                ▼
              ┌─────────────┐                                   ┌─────────────┐
              │  moto :5000 │ ◄────────────────────────────────┤  moto :5000 │
              │ S3 + Glue + │        Hive metastore=glue (adb)  │  S3 (fs.s3) │
              └─────────────┘                                   └─────────────┘
```

### 3.2 Scope (v1)
- 70 operations ship in the model; v1 implements the **control-plane metadata
  operations** and the **query plane** (start/get/list/stop/batch/get-results,
  runtime statistics, named queries, prepared statements, workgroups, data
  catalogs, engine versions, database/table metadata read proxy).
- Athena Studio / notebook / session / calculation / capacity operations are
  **out of scope** and return correctly-shaped errors (ADR-0004).
- State is **in-memory** (ADR-0003).

## 4. Solution Strategy

1. **Protocol**: one FastAPI route `POST /` dispatching on
   `X-Amz-Target: AmazonAthena.<Op>` (ADR-0008), typed schemas mirroring
   `service-2.json`, botocore-parity error serialization.
2. **Engine**: Apache Trino via `POST /v1/statement` + `nextUri` polling
   (ADR-0001). Catalog = Hive connector with `hive.metastore=glue` pointing at
   moto Glue (ADR-0005).
3. **Data plane**: Trino's native S3 filesystem (`fs.s3.enabled=true`) against
   moto S3 (ADR-0006); the emulator additionally writes result artifacts
   itself with boto3 so artifacts are byte-predictable for awswrangler
   (ADR-0007).
4. **State machine**: async tasks per query, `QUEUED→RUNNING→SUCCEEDED|FAILED|
   CANCELLED`, `GetQueryResults` pre-finish returns Athena's exact 400
   (ADR-0009).
5. **Process**: TDD at every code change; toolchain gates at every commit
   (§8.4, §10).

## 5. Building Block View

| Module (under `libs/athena-local/src/athena_local/`) | Responsibility |
|---|---|
| `main.py` | FastAPI app; `POST /` catch-all; `/health` probe; composition root for both planes |
| `dispatch.py` | `X-Amz-Target` → operation handler; registry loaded from the installed botocore Athena model (ADR-0008) |
| `schemas.py` / `common_schemas.py` / `workgroup_schemas.py` | Typed request/response shapes per `service-2.json` |
| `errors.py` | `InvalidRequestException`, `ResourceNotFoundException`, `TooManyRequestsException`, `InternalServerException`; `{"__type", "message"}` + `X-Amzn-Errortype` (ADR-0008) |
| `error_mapping.py` | Trino statement errors → Athena's wire error vocabulary (ADR-0008) |
| `statement_classification.py` | `StatementType`/`SubstatementType` + artifact kind, classified at submit |
| `dialect.py` + `external_table.py` + `partition_alter.py` | Athena→Trino statement spellings (`CREATE/DROP DATABASE` → `SCHEMA`, identifier quoting, trailing `;`, `MSCK REPAIR TABLE` → `CALL system.sync_partition_metadata(…, 'ADD')`, `CREATE EXTERNAL TABLE` → `CREATE TABLE … WITH(…)`, `ALTER TABLE … ADD PARTITION` → `CALL system.register_partition` with `IF NOT EXISTS`→`ALREADY_EXISTS` no-op, `UNLOAD` → CTAS + session codec, ADR-0012) |
| `iceberg.py` + `iceberg_table.py` | Iceberg routing to the dedicated `iceberg` catalog: `TBLPROPERTIES('table_type'='ICEBERG')` CREATE → `WITH(format, location[, partitioning])`; Glue `table_type` marker routes `INSERT`/`MERGE`/`DELETE`/`SELECT`/ALTER references; backtick→`"ident"` normalization; `ADD COLUMNS`/`CHANGE COLUMN` → Trino's single-action ALTERs (ADR-0013) |
| `state.py` / `data_catalog_state.py` | In-memory registries: workgroups, named queries, prepared statements, data catalogs (ADR-0003) |
| `workgroups.py` / `workgroup_payloads.py` | Workgroup ops + payload serialization/defaults |
| `named_queries.py` / `prepared_statements.py` / `data_catalogs.py` / `engine_versions.py` / `tags.py` | Control-plane operation handlers |
| `catalog_metadata.py` | `ListDatabases`/`GetDatabase`/`ListTableMetadata`/`GetTableMetadata` read proxy to moto Glue (ADR-0005) |
| `executions.py` | Execution record + `QUEUED→RUNNING→terminal` transition matrix (ADR-0003, ADR-0009) |
| `executor.py` | Async lifecycle: start preflight, semaphore-bound poll task, writer-before-SUCCEEDED, cancellation (ADR-0009) |
| `prepared_execution.py` | Resolves `EXECUTE name [USING …]` against the workgroup store at submit |
| `query_executions.py` | Query-plane op handlers (`Start/Stop/Get/BatchGet/List/GetResults/GetRuntimeStatistics`) |
| `trino_client.py` | Thin wrapper over `POST /v1/statement`, `GET nextUri`, `DELETE` (ADR-0001; project-owned interface per `AGENTS.md` deps rule) |
| `artifacts.py` | `.csv` / `.txt` / `-manifest.csv` + `.metadata` writers; `DataManifestLocation` (ADR-0007, ADR-0010) |
| `output_targets.py` | INSERT/UNLOAD write-target resolution (Glue `StorageDescriptor.Location`, SQL `TO`) + pre-submit object snapshot; feeds the manifest diff (ADR-0007); drops the UNLOAD temp table through Glue (ADR-0012) |
| `s3_writer.py` | Project-owned interface over the boto3 S3 client; put/list against moto S3 (ADR-0006/0007) |
| `glue_proxy.py` | boto3 client proxying catalog reads to moto Glue (ADR-0005) |

Deployment artifacts (docker/): `athena/Dockerfile` (emulator image),
`trino/` (config.properties, catalog/hive.properties,
catalog/iceberg.properties), `moto/` (Glue overlay + entrypoint shim on
the official image) — wired into compose services `athena` (5001) and
`trino` (8080) beside the existing `moto` (5000) (ADR-0002).

## 6. Runtime View

**SELECT flow** (awswrangler `read_sql_query`):
1. wrangler resolves workgroup via `GetWorkGroup`
   (`awswrangler/athena/_utils.py:158-187`) and posts `StartQueryExecution`
   with `ResultConfiguration.OutputLocation`
   (`awswrangler/athena/_utils.py:89-155`).
2. Emulator: create execution (QUEUED) → spawn async task → Trino
   `POST /v1/statement` with `X-Trino-Catalog: hive`, `X-Trino-Schema: <db>`,
   `X-Trino-User: <principal>`; poll `nextUri`.
3. Emulator writes `{QueryID}.csv` (quoted header row as line 1 — ADR-0010)
   + `.csv.metadata` to moto S3 (ADR-0007) and marks SUCCEEDED.
4. wrangler polls `GetQueryExecution` until terminal (`_utils.py:41`),
   then `GetQueryResults` (header row = `Rows[0]`, stripped at
   `_read.py:357,383`) and/or `s3.read_csv` of the `.csv` (`_read.py:209-238`).

**CTAS flow**: wrangler issues `CREATE TABLE db.t AS WITH(...) AS ...`
(`_utils.py:860-872`); Trino builds partition files in the CTAS
`external_location` under moto S3; emulator writes
`{QueryID}-manifest.csv` (one `s3://` path/line) and reports
`Statistics.DataManifestLocation`
(`_read.py:62-81,135-206`).

**INSERT/UNLOAD flow**: the write target already holds files from earlier
writes, so listing it at completion would over-state the manifest. Before
submitting the statement, the emulator resolves the target (Glue
`StorageDescriptor.Location` for INSERT, the SQL `TO` location for UNLOAD —
parsed from the original text, since the UNLOAD dialect rewrite consumes
the clause) and snapshots its objects; at completion the
`{QueryID}-manifest.csv` lists only the objects that appeared since, so it
names exactly the files the query wrote (`_read.py:135-206`). An
unresolvable target FAILs the execution at artifact write, after Trino's
own analysis error has had its chance to surface. An UNLOAD rides the
engine's writer as a CTAS into a generated `athena_unload_*` table at the
`TO` path; the Glue entry is deleted when the statement ends — strictly
before SUCCEEDED, best-effort on FAILED/CANCELLED — because real UNLOAD
registers no catalog table (ADR-0012).

**Dialect adaptation**: statements Athena accepts but Trino's grammar rejects
(a statement-leading `CREATE/DROP DATABASE`, backtick identifiers, a terminal
semicolon) are rewritten by `dialect.py` at submit; the stored execution text
and its classification keep the query as written (§11).

**Prepared statements**: `EXECUTE name [USING …]` is resolved at submit
against the workgroup's prepared-statement store — each `USING` value binds
verbatim as one parenthesized SQL expression at the `?` markers, because
Trino's protocol has no prepared-statement persistence (measured). A missing
statement or parameter-count mismatch starts the execution FAILED — never a
400 — matching real Athena.

**Managed results**: a workgroup with `ManagedQueryResultsConfiguration.
Enabled=true` resolves no `OutputLocation`; the executor skips the artifact
writer, SUCCEEDED still lands, and the terminal rows are served inline via
`GetQueryResults` — wrangler's managed read path (ADR-0011).

**Cancellation**: `StopQueryExecution` → emulator issues `DELETE` on the
Trino statement and records `CANCELLED` (ADR-0009).

## 7. Deployment View

- `docker-compose.yml` services (ADR-0002):
  - `moto` — `motoserver/moto:5.1.16`, publishes `5000:5000` — S3, Glue, STS.
    `./docker/moto` mounts read-only at `/docker/moto` and the entrypoint shim
    applies the Glue overlay (the column-statistics and user-defined-function
    ops, plus the GetPartitions expression/`_cast` bridges) the Trino Hive
    connector needs — the official image itself is unchanged (§11).
  - `trino` — `trinodb/trino:483`; `docker/trino/config.properties` mounts as
    a file and `docker/trino/catalog/` as a dir (a single dir mount would hide
    the image's own `/etc/trino` files). The `hive` catalog uses
    `hive.metastore=glue` at `http://moto:5000`, region `us-east-1`, static
    keys, `hive.collect-column-statistics-on-write=false` and
    `hive.non-managed-table-writes-enabled=true` (Trino
    `object-storage/metastores.html`); native S3 `fs.s3.enabled=true`,
    `s3.endpoint=http://moto:5000`, `s3.region=us-east-1`,
    `s3.path-style-access=true`, static keys
    (`object-storage/file-system-s3.html`). A second catalog,
    `iceberg.properties`, runs the same Glue metastore + S3 block under
    `connector.name=iceberg` with `iceberg.catalog.type=glue` and
    `iceberg.format-version=2` (Athena creates Iceberg v2 tables;
    ADR-0013). A 4 GiB memory cap keeps the
    image's 80%-of-visible-RAM heap sizing inside the host budget; `/v1/info`
    healthcheck; `depends_on: moto`.
  - `athena` — built from `docker/athena/Dockerfile` (locked `uv export` +
    `pip --require-hashes` install, non-root `10001:10001`, uvicorn serving
    `athena_local.main:app` on `:5001`); env `ATHENA_LOCAL_TRINO_URL` (default
    `http://localhost:8080`, compose `http://trino:8080`),
    `ATHENA_MOTO_ENDPOINT_URL` (default `http://127.0.0.1:5000`, compose
    `http://moto:5000`), `ATHENA_LOCAL_MAX_CONCURRENT_QUERIES` (default 4,
    bounds the executor semaphore); `/health` healthcheck; `depends_on` trino
    `service_healthy` + moto `service_started`.
  - Request hardening: `POST /` rejects bodies over 1 MiB — the canonical
    model's largest member is `QueryString` at 262144 chars — with a shaped
    `InvalidRequestException` before dispatch.
  - `jupyterlab` gets `AWS_ENDPOINT_URL=http://moto:5000` and
    `AWS_ENDPOINT_URL_ATHENA=http://athena:5001`, and `depends_on: athena:
    service_healthy` so a cold `docker compose up` sequences correctly.
- Clients point only Athena traffic at `http://localhost:5001`:
  - boto3/awswrangler: `endpoint_url` / `athena_endpoint_url`
    (`awswrangler/_utils.py:255-280`) / `AWS_ENDPOINT_URL_ATHENA`.
  - AWS CLI: `--endpoint-url` / `AWS_ENDPOINT_URL_ATHENA`.
  - terraform-provider-aws: `AWS_ENDPOINT_URL_ATHENA` (custom endpoints guide).

## 8. Cross-cutting Concepts

### 8.1 Typing
pyright `standard` (repo root `pyproject.toml` `[tool.pyright]`), explicit
types everywhere; schema dataclasses derived/verified against `service-2.json`;
no `any`, no `Dict`.

### 8.2 Errors
`{"__type": "<ExceptionShapeName>", "message": "<text>"}` body +
`X-Amzn-Errortype: <ExceptionShapeName>` header (ADR-0008). The model carries
no `httpStatusCode`; statuses 400/404/429/500 follow AWS-documented codes
(moto `JsonRESTError.code` parity). Any non-`AthenaError` escape inside
`dispatch` maps to a shaped `InternalServerException` 500 plus one
structured-JSON log line — internals never reach the client message.

### 8.3 Logging
Structured JSON for observability; plain text only for CLI-facing output.

### 8.4 Quality gates at every commit
Canonical per-lib pattern = `libs/mlops-shared/Makefile` +
`libs/mlops-shared/pyproject.toml`. Root pre-commit (`/.pre-commit-config.yaml`)
runs ruff-format, ruff `--fix`, deptry (`make dependencies`), import-linter
(`uv run lint-imports`), radon (`make complexity`), and — scoped to
`libs/athena-local/` — bandit, vulture, xenon; semgrep stays per-lib/manual.

| Gate | Command (per-lib) | Enforced by |
|---|---|---|
| Ruff format+lint | `uv run ruff format .` / `ruff check .` | pre-commit |
| Pyright | `uv run pyright src` | `make type-check` |
| Pytest + pytest-bdd | `uv run pytest` | `make test` / pre-commit |
| Coverage (pytest-cov) | `uv run pytest --cov --cov-report=term-missing:skip-covered --cov-fail-under=75` | `make coverage` |
| Complexity (radon) | `radon cc . -s -n C` fail on C+ | pre-commit `make complexity` |
| Maintainability (xenon) | `xenon --max-absolute B --max-modules A --max-average A src` | `make maintainability` |
| Dead code (vulture) | `vulture src` | `make security` |
| Security (bandit + semgrep) | `bandit -q -r src -ll`; `semgrep --quiet --config auto .` | `make security` |
| Imports (import-linter) | `uv run lint-imports` (root contracts) | pre-commit |
| Dependencies (deptry) | `uv run deptry .` | pre-commit |

New lib must be registered in: root `pyproject.toml` `[tool.uv].members` +
`[tool.deptry].known_first_party` + `[tool.importlinter].root_packages` and
root `Makefile` `PACKAGES`.

### 8.5 Dependency wrapping
Trino HTTP client and moto boto3 calls are wrapped behind project-owned thin
interfaces (`trino_client.py`, `glue_proxy.py`, `s3_writer.py`) so third-party
libs never leak into handlers (per `AGENTS.md` deps rule). `main.py` is the
composition root for both planes: it builds the executor over these
boundaries, which is why it is exempt from the "protocol core stays
independent of the query engine" import-linter contract.

## 9. Architecture Decisions

| ADR | Decision |
|---|---|
| [0001](adr/0001-trino-query-engine.md) | Trino is the SQL engine, driven via `/v1/statement` |
| [0002](adr/0002-own-service-own-port.md) | `athena` = own container + own port; moto untouched |
| [0003](adr/0003-in-memory-control-plane-state.md) | Control-plane state in memory only |
| [0004](adr/0004-studio-apis-out-of-scope.md) | Studio/notebook/session/calculation APIs out of scope v1 (shaped errors) |
| [0005](adr/0005-metadata-plane-glue-through-moto.md) | Catalog metadata via Hive metastore=glue + read-proxy to moto Glue |
| [0006](adr/0006-data-plane-native-s3-through-moto.md) | Trino native S3 client → moto S3 (spike-gated) |
| [0007](adr/0007-result-artifacts-and-outputlocation-semantics.md) | Artifact naming/format + `OutputLocation` semantics per wrangler |
| [0008](adr/0008-json11-dispatch-and-error-parity.md) | JSON 1.1 dispatch + botocore-parity errors; no moto internals |
| [0009](adr/0009-async-query-execution-state-machine.md) | Async execution state machine + pre-finish read error parity |
| [0010](adr/0010-csv-header-row-and-bytes.md) | `{QueryID}.csv` carries the quoted header row as line 1 (supersedes ADR-0007's headerless descriptor) |
| [0011](adr/0011-managed-results-skip-s3-artifacts.md) | Managed-results workgroups write no S3 artifacts; rows served inline (carve-out to ADR-0009 #4) |

## 10. Quality Requirements

- **Q1 Wire-parity**: every op response round-trips botocore's stub parser for
  the 70-op model (test against `service-2.json`).
- **Q2 Consumer suites** (test-proven, not sampled): awswrangler
  `read_sql_query`/`to_parquet`/cache/CTAS/prepared statements; AWS CLI
  `athena` commands against `:5001`; boto3 low-level parity.
- **Q3 Typed codebase**: pyright standard with zero violations in `src/`.
- **Q4 Gates green at every commit**: the §8.4 table.
- **Q5 TDD**: every new function has a test; bug fixes add regression tests;
  tests are F.I.R.S.T. (fast, independent, repeatable, self-validating,
  timely); BDD feature files cover cross-tool flows (pytest-bdd).

## 11. Technical Risks

| Risk | Mitigation |
|---|---|
| Trino native S3 client ↔ moto S3 incompatibility (Trino tests only AWS S3/MinIO) | **Handled**: spike-proven before integration — CTAS partition files land on moto S3 and read back through the Hive connector (ADR-0006); the emulator additionally owns artifact writes via boto3 (ADR-0007) |
| Trino Glue metastore needs the column-statistics and `GetUserDefinedFunctions` ops, absent in moto Glue | **Handled**: repo-owned minimal overlay (`docker/moto/glue_overlay.py`, entrypoint shim on the official image) serves the four ops Trino calls; validated end-to-end against the running stack (CTAS → moto S3, `SHOW FUNCTIONS`) |
| moto Glue partition-expression filtering breaks Trino partition pruning: blank GetPartitions `Expression` raises `Unsupported expression ''` (5.1.16 only special-cases `None`) and `_cast` rejects Hive type spellings like `varchar(2)`/`decimal(10,2)` | **Handled**: extension of the same overlay — blank Expression ⇒ no filter (mirroring upstream `#10122`/`4db88f3a4`) and `_cast` normalizes type spellings before delegation; partition-key types are NOT normalized at table registration (real AWS stores `varchar(2)`, wrangler `GetTableMetadata` relies on it). Pinned by overlay regression tests plus a live partitioned-read consumer suite |
| Athena DDL dialect vs Trino grammar: real Athena accepts `CREATE/DROP DATABASE`, backtick identifiers, `MSCK REPAIR TABLE`, and `UNLOAD`, while Trino 483 requires `CREATE/DROP SCHEMA`, double-quoted identifiers, `CALL system.*` procedures, and has no `UNLOAD` at all | **Handled**: `dialect.py` rewrites only statement-leading spellings at submit, preserving classification and the stored execution text; `tests/unit/test_dialect.py` and the consumer suites pin each entry. UNLOAD resolves to a CTAS at its `TO` path plus a `hive.compression_codec` session property, and the generated Glue table is deleted when the statement ends — a bounded catalog-residue delta documented in ADR-0012. New entries to the map are added only with evidence |
| moto appends `{id}.csv` to `OutputLocation` (models.py:140) — must not leak into our paths | **Handled**: ADR-0007 — the emulator owns artifact naming; never delegated to moto |
| 400 "Query has not yet finished" must not fire for wrangler's 1 s poll | **Handled**: ADR-0009 — only pre-finish inline reads fail; `GetQueryExecution`/`BatchGetQueryExecution` always answer |
| Terraform-provider-aws can't be driven locally easily | **Handled** (within the local limit): a pinned AWS SDK Go v2 module plus boto3 drive the provider's five resource-family op shapes (`tests/terraform/`) over the live stack; a real `terraform apply` remains an unclaimed stretch |
| Env-var vs config endpoint precedence surprises | **Handled**: explicit-arg → env-var → compose-default resolution in `main.build_query_executor`/`catalog_metadata`; the endpoint-split suite proves per-service `AWS_ENDPOINT_URL_ATHENA` routes only Athena while global `AWS_ENDPOINT_URL` keeps S3/Glue on moto |
| Trino's Iceberg Glue catalog ↔ moto Glue commit semantics mismatch (iceberg writes `metadata_location`-tracked table versions), and consumers filter columns on markers Trino never writes | **Handled**: spike-proven live before integration — `CREATE`/`INSERT`/`SELECT`/`MERGE`/`DELETE` round-trip through `iceberg.catalog.type=glue` on moto, registering `Parameters.table_type=ICEBERG` (ADR-0013); the overlay injects AWS's `iceberg.field.current` column marker at `create_table`/`update_table` so wrangler's `filter_iceberg_current` reads the real schema; routing per-reference on the Glue marker keeps hive staging tables inside cross-catalog statements |
| In-memory execution/result retention is unbounded — `by_id`, `by_request_token`, and cached result rows never evict, so memory grows with lifetime query volume where real Athena bounds retention (45-day history, ~500-row list windows); measured reuse-scan 131 ms @ 20 000 executions | **Open**: bounded by local-emulator scope today (ADR-0003 in-memory control plane); eviction must preserve `ClientRequestToken` dedup + in-flight execution safety |

## 12. Glossary

| Term | Meaning |
|---|---|
| OutputLocation | S3 prefix/location returned by `GetQueryExecution`; must end `.csv`/`.txt` for wrangler file reads |
| StatementType | `DDL` \| `DML` \| `UTILITY` (drives artifact kind; ADR-0007) |
| DataManifestLocation | `.../{QueryID}-manifest.csv` in `Statistics`, consumed by wrangler for CTAS/INSERT/UNLOAD |
| QueryExecutionState | `QUEUED \| RUNNING \| SUCCEEDED \| FAILED \| CANCELLED` |
| WorkGroup | Athena resource; moto pre-creates `primary` |
| nextUri | Trino client-protocol cursor returned by `POST /v1/statement` |

Sources: service model (README evidence index), Trino client-protocol docs,
AWS Athena "finding output files" docs.