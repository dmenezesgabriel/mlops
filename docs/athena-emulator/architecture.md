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
- Trino officially tests only real AWS S3 and MinIO; moto S3 compatibility is
  an open risk that must be spiked before committing to the S3 link (ADR-0006).

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
| `main.py` | FastAPI app; `POST /` catch-all; health endpoint |
| `dispatch.py` | `X-Amz-Target` → operation handler (ADR-0008) |
| `schemas.py` (generated or hand-verified) | Typed request/response dataclasses per `service-2.json` |
| `errors.py` | `InvalidRequestException`, `ResourceNotFoundException`, `TooManyRequestsException`, `InternalServerException`; `{"__type", "message"}` + `X-Amzn-Errortype` (ADR-0008) |
| `state.py` | In-memory registries: workgroups, named queries, prepared statements, data catalogs, executions (ADR-0003) |
| `executor.py` | async query lifecycle; Trino client; cancellation (ADR-0009) |
| `trino_client.py` | thin wrapper over `POST /v1/statement`, `GET nextUri`, `DELETE` (thin interface owned by the project — per `AGENTS.md` deps rule) |
| `artifacts.py` | `.csv` / `.txt` / `-manifest.csv` + `.metadata` writers; `DataManifestLocation` (ADR-0007, ADR-0010) |
| `output_targets.py` | INSERT/UNLOAD write-target resolution (Glue `StorageDescriptor.Location`, SQL `TO`) + pre-submit object snapshot; feeds the manifest diff (ADR-0007) |
| `s3_writer.py` | project-owned interface over the boto3 S3 client; put/list against moto S3 (ADR-0008) |
| `glue_proxy.py` | boto3 client proxying catalog reads to moto Glue (ADR-0005) |
| `config.py` | dataclass: port, moto_endpoint, trino_endpoint, region, credentials, permissive interval |
| `logging.py` | structured JSON logs; plain text on CLI |

Deployment artifacts (docker/): `Dockerfile` (emulator image), `trino/`
(config.properties, catalog/hive.properties), baked into new compose services
`athena` (5001) and `trino` (ADR-0002).

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
`StorageDescriptor.Location` for INSERT, the SQL `TO` location for UNLOAD)
and snapshots its objects; at completion the `{QueryID}-manifest.csv` lists
only the objects that appeared since, so it names exactly the files the query
wrote (`_read.py:135-206`). An unresolvable target FAILs the execution at
artifact write, after Trino's own analysis error has had its chance to
surface.

**Cancellation**: `StopQueryExecution` → emulator issues `DELETE` on the
Trino statement and records `CANCELLED` (ADR-0009).

## 7. Deployment View

- `docker-compose.yml` additions (ADR-0002):
  - `moto` (existing, port 5000) — S3, Glue, STS.
  - `trino` — image `trinodb/trino:<spike-pinned-tag>`; catalogs: `hive`
    (`hive.metastore=glue`, endpoint `http://moto:5000`, region
    `us-east-1`, static keys) — Trino `object-storage/metastores.html`; S3
    native (`fs.s3.enabled=true`, `s3.endpoint=http://moto:5000`,
    `s3.region=us-east-1`, `s3.path-style-access=true`, static keys) —
    `object-storage/file-system-s3.html`.
  - `athena` (port 5001) — uvicorn serving `athena_local.main:app`;
    `AWS_ATHENA_ENDPOINT=http://athena:5001` for the emulator's own boto3
    proxy; env for moto/trino endpoints.
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
`X-Amzn-Errortype: <ExceptionShapeName>` header (ADR-0008), statuses 400/404/
429/500 per `service-2.json` exception `httpStatusCode`.

### 8.3 Logging
Structured JSON for observability; plain text only for CLI-facing output.

### 8.4 Quality gates at every commit
Canonical per-lib pattern = `libs/mlops-shared/Makefile` +
`libs/mlops-shared/pyproject.toml`. Root pre-commit (`/.pre-commit-config.yaml`)
currently runs ruff-format, ruff `--fix`, deptry (`make dependencies`),
import-linter (`uv run lint-imports`), radon (`make complexity`). The athena
effort adds the missing requested tools (bandit, vulture, xenon) to the lib
gate and to pre-commit; see backlog items QC-*.

| Gate | Command (per-lib) | Enforced by |
|---|---|---|
| Ruff format+lint | `uv run ruff format .` / `ruff check .` | pre-commit |
| Pyright | `uv run pyright src` | `make type-check` |
| Pytest + pytest-bdd | `uv run pytest` | `make test` / pre-commit |
| Coverage (pytest-cov) | `uv run pytest --cov --cov-report=term-missing:skip-covered` | `make coverage` |
| Complexity (radon) | `radon cc . -s -n C` fail on C+ | pre-commit `make complexity` |
| Maintainability (xenon) | xenon against MI thresholds | QC item |
| Dead code (vulture) | `vulture src` | QC item |
| Security (bandit + semgrep) | `bandit -r src -ll`; `semgrep --config auto .` | `make security` |
| Imports (import-linter) | `uv run lint-imports` (root contracts) | pre-commit |
| Dependencies (deptry) | `uv run deptry .` | pre-commit |

New lib must be registered in: root `pyproject.toml` `[tool.uv].members` +
`[tool.deptry].known_first_party` + `[tool.importlinter].root_packages` and
root `Makefile` `PACKAGES`.

### 8.5 Dependency wrapping
Trino HTTP client and moto boto3 calls are wrapped behind project-owned thin
interfaces (`trino_client.py`, `glue_proxy.py`, `s3_writer.py`) so third-party
libs never leak into handlers (per `AGENTS.md` deps rule).

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
| Trino native S3 client ↔ moto S3 incompatibility (Trino tests only AWS S3/MinIO) | ADR-0006; Phase-0 spike proves read/write before integration; emulator writes artifacts itself via boto3 as a guaranteed path |
| Trino Glue metastore needs the column-statistics and `GetUserDefinedFunctions` ops, absent in moto Glue | **Handled**: repo-owned minimal overlay (`docker/moto/glue_overlay.py`, entrypoint shim on the official image) serves the four ops Trino calls; validated end-to-end in M0 step 6 |
| moto appends `{id}.csv` to `OutputLocation` (models.py:140) — must not leak into our paths | ADR-0007: we own artifact naming; never delegate it to moto |
| 400 "Query has not yet finished" must not fire for wrangler's 1 s poll | ADR-0009: only fail pre-finish inline reads; always allow `GetQueryExecution` |
| Terraform-provider-aws can't be driven locally easily | Validate via AWS SDK Go v2 + boto3 op-shape parity tests; provider runs as stretch (backlog TM-*) |
| Env-var vs config endpoint precedence surprises | Config dataclass with explicit priority; tests per consumer contract |

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