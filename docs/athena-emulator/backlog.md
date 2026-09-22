# Backlog — Athena Local Emulator (EPHEMERAL)

> **EPHEMERAL WORK BACKLOG — iterates freely; never cited from code.**
> Every item traces to evidence anchors (research_repos/… and upstream docs).
> DoD = TDD (red→green tests included) + §8.4 gates green at commit.
> Work sizes: S ≤ 1 day · M = 1–3 days · L = 3–5 days.

## A. Repo wiring & quality gates (QC)

| ID | Item | Work | Evidence / contract | Depends |
|---|---|---|---|---|
| QC-1 | [x] Register `libs/athena-local` in root: uv workspace `members`, `[tool.deptry].known_first_party`, `[tool.importlinter].root_packages`, root `Makefile` `PACKAGES` | S | root `pyproject.toml` (`members`, deptry, importlinter), root `Makefile:25`; mirror `sagemaker-local` entry | — |
| QC-2 | [x] Lib skeleton: `src/athena_local/` + `py.typed` + `pyproject.toml` (hatchling, pins per pattern) + `Makefile` (format/lint/type-check/test/coverage/complexity/dependencies/security/quality) | S | `libs/mlops-shared/Makefile`, `pyproject.toml` (canonical pattern); `libs/sagemaker-local` layout | QC-1 |
| QC-3 | [x] Add **bandit, vulture, xenon** to lib gate + dev deps; wire into per-lib `make security`/`quality` and root pre-commit | M | PRD NFR-02; user tooling list; current pre-commit lacks them (`.pre-commit-config.yaml` has ruff/ruff-format/deptry/import-linter/radon only) | QC-2 |
| QC-4 | [x] Import-linter: `athena_local` package-independence contract; boundary contracts (`schemas/errors` vs `executor/artifacts` vs `glue_proxy`) land per-module with each module's first commit | S | root `pyproject.toml [tool.importlinter]` (15 contracts green); ADR-0008; installed import-linter `helpers.py:111-112` raises on contracts referencing not-yet-existing modules | QC-1 |
| QC-5 | [x] Pyright standard baseline: per-lib `uv run pyright src` → 0 errors; CI path = root `make type-check` (loops PACKAGES); no `.vscode/` — Pylance reads `[tool.pyright]` from pyproject | S | root `pyproject.toml [tool.pyright]`; NFR-03 | QC-2 |
| QC-6 | [x] Pytest-bdd harness: `tests/bdd/` + first BDD feature (canonical-model integrity guard, 3 scenarios, green); per-consumer-flow features (wrangler, cli, api) land with the M2/M3 suites | M | Pytest-bdd 8.1.0 patterns; NFR-01; milestones M2/M3 suites | QC-2 |
| QC-7 | Coverage gate: `pytest --cov --cov-report=term-missing:skip-covered`, minimum per-module target (set at M3 close, evidence-based on consumer suites) | S | pattern `libs/mlops-shared` coverage target | QC-2 |

## B. Phase 0 spike (SP) — evidence-gated risks

| ID | Item | Work | Evidence / decision link | Depends |
|---|---|---|---|---|
| SP-1 | [x] Pin Trino tag (**`trinodb/trino:483`**, current stable); boot `trino` container; verify `/v1/statement` round-trip (`SELECT 1` → `[1]`, QUEUED→RUNNING→FINISHED); capture exact tag used | S | trino.io client-protocol; ADR-0001 | — |
| SP-2 | [x] Prove **Trino native S3 ↔ moto S3**: `CREATE TABLE … WITH(external_location='s3://bucket/…')` then `SELECT` returns rows; catalog `hive/hive.properties` with `fs.s3.enabled=true`, `s3.endpoint=http://moto:5000`, `s3.path-style-access=true`, `us-east-1`, static keys — **S3 link proven** (CTAS partition files appear on moto S3 mid-run; external-parquet `SELECT` returns rows); CTAS commit unblocked by the moto Glue overlay (see SP-3) | M | ADR-0006; trino.io `object-storage/file-system-s3.html` — hard gate; if moto S3 fails, stop and review (no preemptive MinIO swap) | SP-1 |
| SP-3 | [x] Prove **Trino Glue metastore ↔ moto Glue**: `CREATE DATABASE`/`CREATE TABLE` via hive catalog with `hive.metastore=glue` + glue endpoint props; `SHOW FUNCTIONS` (probes `GetUserDefinedFunctions` risk) — **RESOLVED**: all four probes green after the repo-owned minimal moto Glue overlay in `docker/moto/` (entrypoint shim on the official image; adds `update`/`delete`/`get_column_statistics_for_table` + `get_user_defined_functions`); decision = overlay over defer (architecture §11); matrix + measurements in milestones M0 step 6 | M | ADR-0005; trino.io `object-storage/metastores.html`; moto Glue ops `models.py:360,1240` | SP-1 |
| SP-4 | Lock hive catalog config files (`config.properties`, `catalog/hive.properties`) as artifacts under `docker/trino/` and commit them | S | SPI output → architecture §7 | SP-2, SP-3 |
| SP-5 | Write spike evidence note (NOT into code) with measured tags, endpoints, errors | S | Dispo: capture to backlog/milestone notes only | SP-2…4 |

## C. Protocol core (PC) — ADR-0008

| ID | Item | Work | Evidence | Depends |
|---|---|---|---|---|
| PC-1 | [x] FastAPI app: single `POST /` route + health; `X-Amz-Target` dispatch table generated/verified from `service-2.json` op names (all 70 present, out-of-scope → shaped errors) | M | ADR-0008; model op list | QC-2 |
| PC-2 | Typed schemas for implemented ops (request/response dataclasses, optionality from model) + fixtures derived from model | M | model `shapes`; NFR-03 | PC-1 |
| PC-3 | [x] Error serializer/parity: `{"__type","message"}` + `X-Amzn-Errortype`, statuses 400/404/429/500 (four shapes, §8.2); unknown target handling. Pre-finish `InvalidRequestException` variant (FR-03) is owned by QE-3 — it needs `GetQueryResults` + execution state | M | moto `core/serialize.py:492,538`; `core/exceptions.py:100`; ADR-0008 | PC-1 |
| PC-4 | Body parsing resilient to content-type variants (`application/x-amz-json-1.1`), charset, empty bodies | S | botocore parsers behavior; moto `core/responses.py:468` | PC-1 |
| PC-5 | JSON logging middleware per §8.3 | S | AGENTS.md Logging | PC-1 |

## D. Metadata/control-plane (MD) — ADR-0003, ADR-0005

| ID | Item | Work | Evidence | Depends |
|---|---|---|---|---|
| MD-1 | [x] Workgroup CRUD + `primary` default + `UpdateWorkGroup` (moto lacks update — we add) | M | FR-09; moto `athena.rst` gaps; wrangler `_utils.py:158-187` | PC-1 |
| MD-2 | [x] Named queries CRUD + BatchGet + pagination (`ListNamedQueries`/`ListQueryExecutions` NextToken) | M | FR-10; CLI examples | PC-1 |
| MD-3 | [x] Prepared statement CRUD + list + batch; RNFE on missing | S | FR-11; wrangler `_statements.py:26-29` | PC-1 |
| MD-4 | [x] Data catalog CRUD (`GLUE/HIVE/LAMBDA`) | M | FR-12 | PC-1 |
| MD-5 | [x] `ListEngineVersions` (pinned list) | S | FR-13; ADR-0004 | PC-1 |
| MD-6 | [x] Tags CRUD | S | FR-16 | PC-1 |
| MD-7 | [x] Catalog read proxy → moto Glue: `list_databases`, `get_database`, `list_table_metadata`, `get_table_metadata` | M | FR-08; ADR-0005 | PC-1, SP-3 |
| MD-8 | [x] `GetWorkGroup` must expose `ResultConfiguration.OutputLocation` handling that wrangler honors (see PC/AD-0007 interplay) — verified: wrangler `_get_workgroup_config` parity tests (`integration/test_workgroups.py:104-156`) + `workgroups.feature` OutputLocation round-trip | S | FR-09; wrangler `_utils.py` config resolution | MD-1 |

## E. Query engine (QE) — ADR-0001, ADR-0009

| ID | Item | Work | Evidence | Depends |
|---|---|---|---|---|
| QE-1 | [x] `trino_client.py` thin wrapper: POST statement, poll nextUri (with `X-Trino-Catalog/Schema/User`), DELETE cancel, map errors | M | trino.io client-protocol; ADR-0001 | PC-1 |
| QE-2 | [x] Async executor + `executions.py` state registry: QUEUED→RUNNING→terminal machine, semaphore bound, records per ADR-0009; unit-verified transitions, writer-before-SUCCEEDED ordering, cancel paths, pre-finish `GetQueryResults` 400 text parity, StatementStats→Statistics mapping | M | ADR-0009; wrangler `_utils.py:41-42` (Trino Stats fields: `client/trino-client/.../StatementStats.java`) | QE-1 |
| QE-3 | [x] `StartQueryExecution` + `StopQueryExecution` + `GetQueryExecution`/`BatchGetQueryExecution` + `GetQueryResults` + `GetQueryRuntimeStatistics` | M | FR-01/02/03/14/15; ADR-0009 | QE-2 |
| QE-4 | [x] Statement classification → `StatementType`/`SubstatementType` (DML/DDL/UTILITY + CTAS/INSERT/UNLOAD detection) | S | ADR-0007; model enums | QE-2 |
| QE-5 | [x] SQL error mapping Trino→Athena (`InvalidRequestException` 400 incl. wrangler-recognizable fragments) | M | FR-18; wrangler `_utils.py:888-898` | QE-1 |

## F. Artifacts (AR) — ADR-0007/0010

| ID | Item | Work | Evidence | Depends |
|---|---|---|---|---|
| AR-1 | [x] `artifacts.py` + `s3_writer.py`: writers for `.csv` (quoted header row as line 1 — ADR-0010 — + `.csv.metadata`), `.txt` (tab, QUOTE_ALL) + `.txt.metadata`, CTAS `-manifest.csv` + `.metadata` via boto3→moto S3; manifest enumerates the CTAS `external_location` from the SQL; BDD + integration acceptance incl. pandas re-read with wrangler's exact args | M | FR-04/05/06; wrangler `_read.py:209-238`, `_utils.py:190-221`, `_read.py:62-81,135-206`; ADR-0010 | QE-2 |
| AR-1a | [x] INSERT/UNLOAD `-manifest.csv` enumeration: exact file list for existing-table writers (list the table location, over-stating files is wrong); `output_targets.py` captures the write target's objects before submit (Glue `StorageDescriptor.Location` for INSERT, `TO` for UNLOAD) and diffs at completion so the manifest lists only the files the query wrote | M | `read.py:135-206` (INSERT example); own evidence | AR-1 |
| AR-2 | [x] `OutputLocation` = full artifact path; write-before-SUCCEEDED ordering; `Statistics.DataManifestLocation` set for manifest ops | M | ADR-0007; AWS docs output-files | AR-1 |
| AR-3 | Inline `GetQueryResults` page semantics (header row, pagination, MaxResults cap, cell encoding) | M | FR-03; wrangler `_read.py:335-384` | QE-3 |
| AR-4 | Type→VarCharValue serialization for all Trino column types (numbers/bools/dates/decimals/timestamps; null → absent key) | S | model `VarCharValue` optional; wrangler dtype mapping | AR-3 |

## G. Consumers (CS)

| ID | Item | Work | Evidence | Depends |
|---|---|---|---|---|
| CS-1 | Assert boto3/botocore parity: loop all 70 ops against service-2.json through stubs against `:5001` | M | README evidence index; ADR-0008 | PC/CMD/QE/AR done |
| CS-2 | awswrangler suite: `read_sql_query` (api + csv), cache, `to_parquet`/CTAS, prepared statements, workgroup config, bad-SQL error path — in docker pytest against running stack | L | FR matrix; wrangler evidence anchors | E/QE/AR |
| CS-3 | AWS CLI `athena` suite: examples from `research_repos/aws-cli/awscli/examples/athena/` via `--endpoint-url` | M | CLI evidence index | PC…AR |
| CS-4 | terraform-provider-aws: op-shape parity via AWS SDK Go v2 + boto3 (resources `aws_athena_*`); stretch: real `terraform apply` if provider runnable locally | M–L | TF core = CLI only (`research_repos/terraform/main.go`); registry docs | CS-1 |
| CS-5 | Endpoint-routing test: Athena-only traffic → `:5001`; S3/Glue → moto `:5000` unchanged | S | ADR-0002; PRD FR-19 | CS-2 |

## H. Deployment & docs (DP)

| ID | Item | Work | Evidence | Depends |
|---|---|---|---|---|
| DP-1 | `docker/` for `athena` image (uvicorn entrypoint) + `trino` configs from SP-4 | M | architecture §7; ADR-0002 | SP-4 |
| DP-2 | Extend `docker-compose.yml`: `trino` + `athena` services on `mlops_net`, port 5001; env wiring | M | ADR-0002; existing compose | DP-1 |
| DP-3 | README (lib usage: endpoint env vars per consumer; compose up flow; reset semantics ADR-0003) | S | PRD NFR-09 | DP-2 |
| DP-4 | Docs sync check: permanent docs (architecture.md, adr/) updated as design moves; ephemeral docs never enter code | S | README doc map | DP-2 |
| DP-5 | Hardening: request size limits, asyncio bound (QE-2), graceful error on trino-down, health endpoint for compose depends_on | M | AGENTS.md Logging; NFR-10 | QE/AR |

## Definition of Done (all items)

- Red→green test written first (TDD) — regression test where bug fix.
- Final commit passes: `make format lint type-check test coverage complexity dependencies security` + `uv run lint-imports`; bandit/vulture/xenon where wired (QC-3).
- No moto internals imported (ADR-0008); no ephemeral doc references in code.