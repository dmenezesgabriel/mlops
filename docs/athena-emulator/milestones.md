# Milestones — Athena Local Emulator (EPHEMERAL)

> **EPHEMERAL — iterates; never cited from code.** Steps reference backlog IDs
> (backlog.md) and evidence. TDD is mandatory at every code change within every
> step. Milestones build in order; each milestone's exit gate = §8.4 gates
> green (per-lib `make quality` + pre-commit), plus explicit exit criteria.

## M0 — Spike: prove the risky links (backlog SP-*)

Goal: de-risk ADR-0005 (Glue metastore) and ADR-0006 (native S3 ↔ moto S3)
before any integration code. Spike code is throwaway in a scratch dir (never
`src/`); evidence is captured as notes (SP-5), never in code comments.

Steps:
1. [x] Pin Trino tag (`trinodb/trino:483`), boot `trino` alone against moto (SP-1).
   - Verified 2026-09-19: `POST /v1/statement` `SELECT 1`, `nextUri` chain
     QUEUED→RUNNING→FINISHED, rows `[[1]]`, column `_col0 integer`.
   - Evidence: trino.io `develop/client-protocol.html` (statement API),
     ADR-0001.
2. Configure `catalog/hive.properties`: `hive.metastore=glue`,
   `hive.metastore.glue.endpoint-url=http://moto:5000`,
   `hive.metastore.glue.region=us-east-1`, static creds; native S3
   `fs.s3.enabled=true`, `s3.endpoint=http://moto:5000`,
   `s3.region=us-east-1`, `s3.path-style-access=true`, static creds (SP-2/3).
   - Evidence: trino.io `object-storage/metastores.html`,
     `object-storage/file-system-s3.html`; ADR-0005/0006.
3. Round-trip: `CREATE DATABASE` + `CREATE TABLE … WITH(external_location='s3://athena-results/…') … AS SELECT`
   then `SELECT` back; verify rows land on moto S3 (SP-2, SP-3).
   - Evidence: moto Glue ops `research_repos/moto/moto/glue/models.py:360,1240`;
     moto S3.
4. Probe `SHOW FUNCTIONS` and a DDL to test Trino's
   `GetUserDefinedFunctions` usage against moto Glue (SP-3): the confirmed risk
   in architecture §11.
5. Commit only the pinned tag + proven `docker/trino/` configs (SP-4).
6. [x] Known-failure matrix (spike results) + resolution: both data-plane links proven —
   CTAS parquet files observed on moto S3 mid-run; external-parquet SELECT
   returns rows. Three moto Glue APIs (5.1.16 and master) were missing and
   confirmed as the blocker: column-statistics (`update`/
   `delete`/`get_column_statistics_for_table`) and
   `get_user_defined_functions`; the singular `get_user_defined_function`
   also stays absent (out of scope, no flow needs it). Trino calls `updateTableStatistics(OVERWRITE_ALL)`
   unconditionally after every create-table commit
   (`SemiTransactionalHiveMetastore.CreateTableOperation`), so no catalog
   property avoids it. Decision: repo-owned minimal overlay in `docker/moto/`
   — entrypoint shim on the official `motoserver/moto:5.1.16` image (unpinned
   build) serving exactly those four ops (architecture §11 mitigation).
   Verified 2026-09-19 against the running stack: CTAS
   `WITH(external_location='s3://athena-results/spike-ctas/')` → SUCCEEDED
   (`[[2]]` rows); `SELECT` back → `[[1,"alpha"],[2,"beta"]]`; parquet file
   present on moto S3 (`ListObjectsV2`); `SHOW FUNCTIONS FROM hive.analytics`
   → 0 UDF rows (no 500); `SHOW FUNCTIONS` → 900 built-ins; managed
   `CREATE TABLE` on a located Glue database commits clean.

**Exit criteria:** CTAS partitions readable from moto S3 via Trino; catalog
DDL visible via moto Glue; known-failure matrix (incl. GUDF) documented in
notes. If SP-2 hard-fails → stop, revisit store choice with user (ADR-0006).

## M1 — Skeleton + quality gates (QC-*)

Steps:
1. [x] QC-2: scaffold `libs/athena-local` (src layout `py.typed`, pyproject
   hatchling, Makefile canonical) — mirror `libs/mlops-shared`.
2. [x] QC-1: register in root workspace/members/PACKAGES/deptry/importlinter.
3. [x] QC-3: add bandit, vulture, xenon; wire per-lib targets + pre-commit.
   - Verified 2026-09-19: pinned `bandit==1.9.4`, `vulture==2.16`, `xenon==0.9.3`
     in root dev group; athena-local `security` = `bandit -r src -ll` + `vulture
     src` + `semgrep --config auto .`, new `maintainability` = `xenon
     --max-absolute B --max-modules A --max-average A` (per §8.4); all three
     wired as pre-commit hooks scoped to `libs/athena-local/`; semgrep stays
     per-lib/manual.
4. [x] QC-4/5/6: import-linter contracts, pyright baseline, pytest-bdd features
   vs config file.
   - Verified 2026-09-19: `athena_local` independence contract added (15
     contracts green); pyright standard 0 errors (`uv run pyright src`);
     pytest-bdd harness green — 3 scenarios in `tests/bdd/canonical_model.feature`
     (installed botocore model byte-identical to the reference, 70 ops,
     JSON-1.1), per-flow features land with M2/M3. Docs also corrected on the
     measured wire literal: `X-Amz-Target` is `AmazonAthena.<Op>` (captured
     from a live boto3 request), not `Athena_2017_05_18.<Op>`.
5. [x] PC-1: FastAPI `POST /` catch-all + health; empty dispatch (all 70 targets →
   shaped `InvalidRequestException`) with PC-3 error serializer; first
   end-to-end test: botocore stub call to `:5001` parses error.
   - Verified 2026-09-19: dispatch registry loads the 70 op names from the
     installed botocore Athena model (public `ServiceModel.operation_names`);
     `POST /` answers every one of the 70 targets with
     `InvalidRequestException` 400 (`__type`+`message` body,
     `X-Amzn-Errortype`, `application/x-amz-json-1.1`); `GET /health` → 200;
     unknown/missing `X-Amz-Target` → shaped 400 naming the segment. Smoke:
     threaded uvicorn on a random port + real boto3 client,
     `list_engine_versions()` → same shaped `InvalidRequestException`/400
     round-trip (95 tests, 99% cov, all §8.4 gates green). Provenance
     correction: `service-2.json` carries no `httpStatusCode` (0 hits) — the
     400/404/429/500 codes are AWS-documented statuses (moto `JsonRESTError
     .code`); ADR-0008 text left as-is (append-only rule).

Exit: `make quality` green from a fresh checkout; repo pre-commit green;
stub-driven smoke test passes (botocore stub → JSON-1.1 error round-trip).

## M2 — Control-plane & metadata API (MD-*)

Steps (each TDD):
1. [x] MD-1 workgroups (incl. `primary` default, `UpdateWorkGroup`) —
   wrangler-config parity test using `_get_workgroup_config`
   (`awswrangler/athena/_utils.py:158-187`).
2. [x] MD-2 named queries (+ pagination), MD-3 prepared statements (RNFE policy
   per `awswrangler/athena/_statements.py:26-29`), MD-4 data catalogs,
   MD-5 engine versions, MD-6 tags.
3. [x] MD-7 catalog read proxy to moto Glue (needs M0 SP-3 proven); parity test:
   AT data create via CLI then `list_table_metadata` returns the same table
   (integration suite covers Glue-write → API-read single-store parity).
4. [x] BDD features for each flow (`tests/bdd/`).

Exit: metadata ops green against botocore stubs AND awswrangler config path;
CLI `athena list-*` examples pass.

## M3 — Query engine + artifacts (QE-*, AR-*)

Steps:
1. [x] QE-1 `trino_client.py` (statement POST / poll / DEL). Test with fake
   transport (F.I.R.S.T., no docker needed in unit tests).
   - Verified 2026-09-20: httpx AsyncClient + MockTransport, 15 unit tests pin POST
     body/session headers, nextUri GET poll, DELETE cancel (204), retry on
     429/502/503/504 + empty-200 (Retry-After honored, capped), query `error` carried
     in the page as data (mapper-owned later), transport failures → TrinoTransportError.
2. [x] QE-2 async executor + state registry (ADR-0009). Unit tests: state
   transitions, pre-finish `GetQueryResults` 400 text parity.
   - Verified 2026-09-20: `executions.py` (record+store, transition matrix
     QUEUED→RUNNING→terminal, terminal states immutable, StatementStats
     `processedBytes`/`wallTimeMillis` → Statistics per trino
     `client/trino-client/.../StatementStats.java`) + `executor.py` (`start`
     sync, semaphore-bound background task, writer-before-SUCCEEDED ordering,
     CANCELLED via DELETE incl. QUEUED/RUNNING windows, exact 400
     `Query has not yet finished. Current state: <state>`). 29 new unit tests;
     import-linter boundary contract added; all §8.4 gates green.
3. [x] QE-3 ops (`Start/Stop/Get/BatchGet/GetResults/GetRuntimeStatistics`),
   QE-4 statement classification, QE-5 error mapping.
   - Verified 2026-09-21 (QE-3/4): the six QE-3 ops bound to the dispatch
     registry on commit `2726ece`; `StatementType`/`SubstatementType`
     classified at submit for QE-4 — DML/DDL/UTILITY per the model enum
     (`service-2.json:4689-4696`), free-form `SubstatementType`
     (`:3922-3925`), CTAS→DDL + UNLOAD→DML honoring wrangler
     `_read.py:912-934`; 443 unit tests, 99% cov, all §8.4 gates green.
   - Verified 2026-09-21 (QE-5): `start` runs a bounded preflight (submit +
     one nextUri fetch) so syntax errors reject StartQueryExecution before
     any execution exists with the shaped 400 `Exception parsing query:
     <trino message>` (`error_mapping.py`); analysis/transport outcomes
     forward into the poll task (no re-submit) and FAIL the execution with
     Trino's StateChangeReason verbatim; `Trino unreachable` preserves the
     QE-2 FAILED contract. Unit + one live-stack integration test (boto3 →
     uvicorn → real Trino: bad-SELECT 400 + dup-column CTAS FAILED reason);
     451 tests, 99% cov, all §8.4 gates green.
   - Regression anchor: wrangler's bad-SQL expectations
     (`awswrangler/athena/_utils.py:888-898`).
4. [x] AR-1..4 artifact writers + OutputLocation semantics + inline pagination.
   - Contract tests: files byte-compare to wrangler expectations (QUOTE_ALL,
     csv with the quoted header row as line 1 — ADR-0010; tab TXT; manifest
     → `.metadata` via `.replace` at `awswrangler/athena/_read.py:153`).
   - Verified 2026-09-21 (AR-1): `artifacts.py` + `s3_writer.py` write the
     three artifact shapes via boto3→moto S3; CTAS manifest enumerates the
     SQL `external_location`; 473 tests (17 new unit + 3 live-moto integration
     + 2 BDD), incl. a pandas re-read of the csv with `_fetch_csv_result`'s
     exact args (dtypes round-trip); all §8.4 gates green.
   - Verified 2026-09-21 (AR-1a): INSERT/UNLOAD manifests list only the files
     the query wrote. `output_targets.py` resolves the write target (Glue
     `StorageDescriptor.Location` for INSERT, the `TO` location for UNLOAD)
     and snapshots its objects before the Trino submit; `artifacts.py` emits
     the completion-time after-minus-before diff. Unresolvable targets leave
     a reason that FAILs the write, so Trino's analysis error surfaces first.
     509 tests (33 new unit + 1 live-moto integration + 2 BDD), all §8.4
     gates green.
    - Verified 2026-09-22 (AR-2): `GetQueryExecution.ResultConfiguration.
      OutputLocation` reports the full artifact path — `{prefix}{QueryID}.csv`
      (DML), `.txt` (DDL/UTILITY), bare `{prefix}{QueryID}` stem for
      CTAS/INSERT/UNLOAD with `Statistics.DataManifestLocation` naming the
      `-manifest.csv` (ADR-0007 #2; wrangler `endswith` gates `_read.py:220`,
      `_utils.py:196`); shared statement→artifact-kind mapping in
      `statement_classification.artifact_output_kind`; 520 tests (8 new unit
      + 1 BDD + 2 live boto3→uvicorn→Trino→moto-S3 integration), 99%
      coverage, all §8.4 gates green.
    - Verified 2026-09-22 (AR-3): inline `GetQueryResults` pagination — header
      row on page zero only, `MaxResults` 1..1000 (out-of-range → shaped 400),
      opaque `NextToken` data-row offset (bad/negative → shaped 400), token
      absent when pages exhaust; a live botocore `get_query_results` paginator
      over boto3→uvicorn→Trino→moto-S3 merges a 6-row `VALUES` SELECT split at
      `MaxResults` 2 losslessly (wrangler's `_fetch_api_result` path,
      `_read.py:335-384`). During verification the live path surfaced a
      pre-existing QE defect: the poll task cached only the last Trino
      statement page, whose `data` is null for real queries (rows stream on
      intermediate RUNNING pages — measured), so inline results and result
      `.csv`s were header-only; fixed as QE-6 (rows folded from the POST
      response + accumulated across polled pages). 539 tests (11 new unit +
      3 BDD + 2 live integration + 2 executor regression), all §8.4 gates
      green.
   - Verified 2026-09-22 (AR-4): per-type VarCharValue serialization in
     `query_executions._cell_value` — numbers/decimals/dates/timestamps
     arrive from Trino already in Athena's string shape and pass through,
     booleans normalize to the lowercase wire form, and a null cell renders
     as an empty datum (no `VarCharValue` member, per the model's optional
     `Datum.VarCharValue`) instead of `""`. Live proof: a real-engine SELECT
     of integer/boolean/double/decimal(6,2)/date/timestamp/NULL columns
     returns `"1"`, `"true"`, `"1.5"`, `"12.34"`, `"2023-06-15"`,
     `"2023-06-15 10:20:30.123"`, and `{}` over boto3→uvicorn→Trino.
     542 tests, 99% coverage, all §8.4 gates green.
5. Integration: Docker stack, `SELECT` via wrangler end-to-end (M0 config).
   - **Split into tracked backlog items (2026-09-22):** PC-6 (query-plane
     composition root in `main.py`) → QE-7 (server-side prepared-statement
     execution) → MD-9 (managed-results workgroup → `StartQueryExecution`
     without `OutputLocation`) → CS-2b (awswrangler consumer suite: api/csv/
     cache/prepared/bad-SQL/to_parquet against the running moto container via
     bridge IP). The step closes when CS-2b is green.
    - Verified 2026-09-22 (QE-7): `prepared_execution.py` parses
      `EXECUTE <name> [USING …]`, binds each value **verbatim** as one
      paren-wrapped SQL expression into the stored `QueryStatement` at its `?`
      markers (scanning skips `?` inside literals/comments), and resolves the
      workgroup-scoped store at submit (Trino's protocol has no
      prepared-statement persistence — measured). Missing statement →
      `PreparedStatement {name} was not found in workGroup {workgroup}`;
      `?`-count mismatch → `Incorrect number of parameters: expected N but
      found M`; both start FAILED (never 400) with the submitted EXECUTE text
      as the wire `Query`, while success submits the bound statement and
      classifies from it (EXECUTE-of-SELECT → DML/SELECT → the `.csv` naming
      wrangler gates on). Live proof: prepared statement created via boto3,
      `EXECUTE "st" USING 'Washington'` → SUCCEEDED with `Query` preserved,
      DML/SELECT, inline rows + `.csv`/`.metadata` on moto S3 over
      boto3→uvicorn→Trino; missing statement and count mismatch → FAILED.
      584 tests, 99% coverage, all §8.4 gates green.

Exit: wrangler `read_sql_query` (api + csv + cache), `to_parquet` CTAS,
prepared statements, bad-SQL error path — all green against the docker stack.

## M4 — Full consumer validation (CS-*)

Steps:
1. CS-1 botocore 70-op loop against `:5001` (stubs + real transport).
2. CS-2 awswrangler complete suite (incl. partitioned reads FR-07, cache).
3. CS-3 AWS CLI examples suite (`awscli/examples/athena/`).
4. CS-4 terraform op-shape parity (SDK Go v2 + boto3); stretch: real
   provider apply if feasible — evidence-gated, no invention.
5. CS-5 endpoint-routing split test.

Exit: all consumer suites green on CI with the docker stack; any mismatch logs
an evidence-gated fix (PRD FR matrix) — no silent deviation.

## M5 — Deployment, docs, hardening (DP-*)

Steps:
1. DP-1/2 docker images + compose services (`athena` :5001, `trino`) on
   `mlops_net`; env wiring.
2. DP-3 lib README (consumer endpoint env vars, compose flow, reset semantics).
3. DP-5 hardening: limits, semaphore bound, trino-down graceful errors, health
   endpoint for compose depends_on.
4. DP-4 permanent-doc sync (architecture §7 deployment, ADRs as-built).

Exit: `docker compose up` → jupyterlab + moto + athena + trino; full M4 suite
green from a cold stack; permanent docs current.

## Sequence & dependencies

```
M0 (SP) → M1 (QC/PC core) → M2 (MD) → M3 (QE/AR) → M4 (CS) → M5 (DP)
```
Blockers gating start: M0 SP-2/SP-3 must pass before QE/AR integration (M3).
M2 MD-7 needs SP-3. QC gates (M1) precede any src/ code per NFR-01/02.