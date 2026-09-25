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
     without `OutputLocation`) → CS-2b1/CS-2b2 (awswrangler consumer suites
     against the running moto container via bridge IP: CS-2b1 = read paths
     api/csv/cache/bad-SQL, CS-2b2 = prepared EXECUTE + `to_parquet` CTAS).
     The step closes when CS-2b2 is green.
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
     - Verified 2026-09-24 (MD-9): managed-results workgroup — a
       `StartQueryExecution` with no `ResultConfiguration` no longer 400s; the
       execution stores an empty `ResultConfiguration`, `GetQueryExecution`
       reports it without `OutputLocation` (the exact shape wrangler's managed
       tests assert, `awswrangler/tests/unit/test_athena.py:125`), the writer
       is skipped yet SUCCEEDED still lands with the cached rows served inline
       via `GetQueryResults` (wrangler's managed read path, `_read.py:450,928`),
       and a request-carried `OutputLocation` is ignored (ADR-0011). Live
       proof: boto3 → uvicorn → Trino → moto, with `wr._get_workgroup_config`
       over `create_work_group` reading `managed_results is True`; 591 tests,
       99% coverage, all §8.4 gates green.
     - Verified 2026-09-24 (CS-2b2): wrangler write-path consumer suite green
       on the live stack (in-process uvicorn + bridge moto as shared data
       plane): `params` + `paramstyle="qmark"` prepared `EXECUTE` (bare values
       like `"Washington"` bind as string literals while `"1"`/`DATE
       '2020-01-01'` travel as their typed literals — the spellings wrangler's
       real-AWS suite pins, `awswrangler/tests/unit/test_athena.py:936-937`),
       direct `?`-marker binding, `to_parquet` CTAS round-trip
       (`Statistics.DataManifestLocation` manifest → parquet read-back),
       CTAS + qmark combined, and the parameter-count-mismatch FAILED
       execution (`QueryFailed` on the wrangler side, never a 400). Live
       proof: `read_sql_query`/`create_ctas_table` through boto3 → uvicorn →
       Trino → moto; 6 CS-2b2 + 4 CS-2b1 integration tests against the live
       stack, 514 unit tests, 99% coverage, all §8.4 gates green. The step
       closes here (CS-2b2 green).

Exit: wrangler `read_sql_query` (api + csv + cache), `to_parquet` CTAS,
prepared statements, bad-SQL error path — all green against the docker stack.

## M4 — Full consumer validation (CS-*)

Steps:
1. [x] CS-1 botocore 70-op loop against `:5001` (stubs + real transport).
   - Verified 2026-09-24 (CS-1): `tests/_parity.py` inflates a model-valid
     request body for every operation straight from botocore's installed
     Athena model (`service-2.json`) — required members only, passed through
     botocore's own `validate_parameters`, so the loop never sends a request
     the canonical model rejects (inflater gaps fail the stub test with the
     offender shape, not a server mystery). Two layers consume the same
     stubs: the dispatch-level loop (210 TestClient cases) drives all 70 ops
     with real inflated bodies and cross-checks the not-yet-implemented vs
     implemented marker boundary from `dispatch.OPERATION_HANDLERS`; the
     real-transport loop (70 cases) serializes each stub through a real boto3
     client over HTTP against a module-scoped in-process uvicorn server (no
     Trino/moto required — the goal), or the compose `athena` :5001 service
     via `ATHENA_LOCAL_TEST_ENDPOINT`, which is how M4 pins the deployed
     stack. Run budget: the loop surfaced no unmodeled 500s or shape drift —
     the parity contract already held — and now guards it on every commit.
     Measured outcome mix across the 70 ops: 16×200 success, 48×400
     `InvalidRequestException`, 4×500 `InternalServerException` (the four
     catalog-introspection reads reach the Glue boundary — moto-down answers
     the shaped error, moto-up serves real data), 2×404
     `ResourceNotFoundException`; zero unmodeled errors, zero
     transport/parse failures. Retries disabled on both test clients so the loop asserts the
     FIRST response (botocore would otherwise retry a modeled 500 as a
     transient error); 917 tests, 99% coverage (QC-7 gate now enforced,
     `--cov-fail-under=75`), all §8.4 gates green.
2. [x] CS-2 awswrangler complete suite (incl. partitioned reads FR-07, cache).
   - Closed 2026-09-24 by CS-2b1 (read), CS-2b2 (write), CS-2b3 (partitioned).
   - Verified 2026-09-24 (CS-2b3): the partitioned-read suite runs through the
     emulator against the **running compose moto container** (restarted to
     load the overlay, `docker compose restart moto`) + Trino 483. The moto
     Glue overlay now bridges both GetPartitions gaps that blocked FR-07:
     moto 5.1.16 raised `Unsupported expression ''` on every blank Expression
     the Hive metastore client sends (list-all reads, `"sales$partitions"`,
     `SHOW STATS FOR`) and `Unknown type : 'varchar(2)'` on filter-pruned
     reads — the overlay mirrors upstream `#10122`/`4db88f3a4` and normalizes
     Hive type spellings (`varchar(2)`, `decimal(10,2)`, `timestamp(3)`,
     `char(N)` + double/float/real/boolean/integer) before moto's `_cast`.
     5 live consumer tests green (partitioned CTAS registers `varchar(2)` +
     `decimal(10,2)` keys, full read 3 rows, `WHERE region='EU'` and
     `WHERE amount=10.5` pruned reads 1 row each, `"sales$partitions"`
     virtual table 3 rows) + 4 overlay regression tests (docker/moto,
     `make -C docker/moto test`). New integration coverage shows moto's
     `"table$partitions"` is the `SHOW PARTITIONS` gap-workaround Trino 483
     offers; breakout reflected in backlog CS-2b3.
3. [x] CS-3 AWS CLI examples suite (`awscli/examples/athena/`).
   - Closed 2026-09-25: 31/31 doc commands across all 28 example files run
     green through the installed `awscli==1.46.1` console script with
     `--endpoint-url` at the live stack (in-process uvicorn + bridge moto as
     shared data plane, same as CS-2b). The suite restarted nothing: all five
     chains (workgroups, data catalogs, named queries, catalog metadata/Glue,
     query executions) passed against the already-running Trino 483 + moto.
     CREATE DATABASE (start-query-execution example 2, valid Athena DDL) was
     rejected by Trino's grammar — evidence-gated fix `dialect.py` submits it
     as CREATE SCHEMA while the execution record keeps the original text;
     row added in architecture §11. DML example 1 turned SUCCEEDED ≈446 ms
     after start via CLI get-query-execution polling.
4. [x] CS-4 terraform-provider-aws op-shape parity (AWS SDK Go v2 + boto3).
   - Verified 2026-09-25: the committed `tests/terraform/` module pins the
     provider's SDK versions (`athena v1.66.0`, base `v1.47.0`, config
     `v1.33.5`, credentials `v1.20.5`) and drives the five resource families
     (`aws_athena_database`, `workgroup`, `named_query`, `data_catalog`,
     `prepared_statement`) through their create/read/update/delete operation
     shapes over the live Trino 483 + bridge-moto stack. The Python wrapper
     runs the real Go subprocess first, then repeats the family witnesses with
     boto3; the Go and boto3 runs are green.
   - The provider's database DDL (`CREATE DATABASE` and `DROP DATABASE` with
     backtick identifiers and semicolons) exposed a live Trino mismatch:
     Trino requires `SCHEMA`, double-quoted identifiers, and no statement
     terminator. The evidence-gated `dialect.py` fix and regression test
     preserve the original query text in `QueryExecution.Query` while adapting
     only the submitted statement. `make quality` is green (942 passed, 98%
     coverage).
   - Real `terraform apply` / provider execution was not available locally and
     remains an explicit stretch, not claimed as evidence.
5. [x] CS-5 endpoint-routing split test.
   - Verified 2026-09-25: boto3, awswrangler, AWS CLI, and the pinned AWS SDK Go v2 make live calls through distinct ephemeral Athena/moto endpoints. Global `AWS_ENDPOINT_URL` routes S3/Glue to moto; `AWS_ENDPOINT_URL_ATHENA` routes only Athena to the emulator. The existing provider-shaped Go parity test also runs through the standard SDK environment path; no real `terraform apply` is claimed.
   - Sequential quality gate: 947 tests passed, 98% coverage (98.34% total), Ruff/Pyright/complexity/dependency/security/maintainability targets green, and root `uv run lint-imports` kept all 20 contracts.

Exit: all consumer suites green on CI with the docker stack; any mismatch logs
an evidence-gated fix (PRD FR matrix) — no silent deviation.

## M5 — Deployment, docs, hardening (DP-*)

Steps:
1. [x] DP-1/2 docker images + compose services (`athena` :5001, `trino`) on
   `mlops_net`; env wiring.
2. [x] DP-3 lib README (consumer endpoint env vars, compose flow, reset semantics).
   - Verified 2026-09-25: `libs/athena-local/README.md` covers compose up
     (`mlops_net`, `moto`/`trino`/`athena`, `/health`), server env vars with
     defaults + compose values, per-consumer endpoint env vars (boto3,
     awswrangler, AWS CLI, terraform-provider-aws) with S3/Glue on moto, and
     ADR-0003 in-memory reset semantics.
3. [x] DP-5 hardening: limits, semaphore bound, trino-down graceful errors,
   health endpoint for compose depends_on.
   - Verified 2026-09-25: 1 MiB request-body cap + model `QueryString` max
     (262144) enforced as shaped 400s; `ATHENA_LOCAL_MAX_CONCURRENT_QUERIES`
     wires the QE-2 semaphore bound (default 4); a `dispatch` catch-all turns
     any non-`AthenaError` escape into a shaped `InternalServerException` 500
     with a structured-JSON log (the S3WriterError-on-moto-down leak); compose
     `athena` has an explicit healthcheck and jupyterlab `depends_on` it.
     Live-verified on the rebuilt container; `make quality` green (956
     passed, 97.65% cov), lint-imports 20/20.
4. [x] DP-4 permanent-doc sync (architecture §7 deployment, ADRs as-built).
   - Verified 2026-09-25: ephemeral IDs removed from all code (~150 sites:
     `src/` docstrings/comments, `tests/` incl. `.feature` titles and seed
     literals, `docker/moto/`, `pyproject.toml` contract comment);
     `architecture.md` synced to as-built (module table, deployment view,
     gate table, §9 ADR index, §11 risks all handled, §8.2 status-code
     provenance corrected); errata/as-built notes on ADR-0008/0003/0006.
     Repo-wide grep outside the ephemeral docs returns zero hits.

Exit: `docker compose up` → jupyterlab + moto + athena + trino; full M4 suite
green from a cold stack; permanent docs current.

## M6 — Jupyter notebook parity validation (NB-*)

Goal: human-facing, evidence-recording notebooks run inside the compose
`jupyterlab` service driving common boto3 + awswrangler flows against the live
stack; each feature records a measured PASS/FAIL/GAP. Notebooks complement the
CS-* pytest suites — they are the readable parity matrix, not a replacement.

Steps:
1. [x] NB-1 scaffold `projects/athena_emulator/` + jupyterlab up + smoke
   notebook (endpoint routing, `SELECT 1` round-trip, moto artifact).
   - Verified 2026-09-25: `docker compose up -d jupyterlab` (depends_on athena
     healthy) → :8888 serving; kernel env awswrangler 3.17.1 / boto3 1.42.82 /
     pandas 2.3.3. nbclient run in-container: routing probe PASS
     (`meta.endpoint_url`), `SELECT 1` SUCCEEDED in 517 ms, `.csv` +
     `.csv.metadata` on moto S3, wrangler csv-path read → (1,2) frame.
     Executed notebook + generated `PARITY.md` committed as evidence.
2. [x] NB-2 boto3 control-plane notebook.
   - Verified 2026-09-25: `02_boto3_control_plane.ipynb` executes clean
     in-container via the nbclient `integration` hook — 14 probes, 12 PASS /
     2 measured GAPs. Enforced workgroup `OutputLocation` overrides the
     client-passed prefix (artifact lands under the workgroup prefix only),
     non-enforced falls back, managed-results reports `ResultConfiguration`
     with no `OutputLocation` and writes nothing to S3, prepared statements
     answer `ResourceNotFoundException` 404, `AwsDataCatalog` is seeded, and
     the ARN tag error taxonomy holds (404 unknown / 400 malformed and
     non-taggable). Two GAPs recorded for NB-6 triage, not worked around:
     `StartQueryExecution` on a `DISABLED` workgroup reaches SUCCEEDED
     (state never checked at submit) and `ListWorkGroups` ignores
     `MaxResults`/`NextToken`.
3. [ ] NB-3 boto3 query lifecycle + DDL + error paths notebook.
4. [ ] NB-4 awswrangler read-path notebook (incl. unload/MSCK/`SHOW PARTITIONS`
   probes — measured outcome recorded, never worked around).
5. [ ] NB-5 awswrangler write/catalog notebook + consolidated parity matrix.
6. [ ] NB-6 file a backlog item per measured FAIL/GAP for triage.

Exit: every notebook executed green inside `jupyterlab` via the
`integration`-marked nbclient hook (and host fallback over localhost ports);
`PARITY.md` lists each probed feature with its measured status; each measured
gap has a backlog item or a documented waiver.

## Sequence & dependencies

```
M0 (SP) → M1 (QC/PC core) → M2 (MD) → M3 (QE/AR) → M4 (CS) → M5 (DP) → M6 (NB)
```
Blockers gating start: M0 SP-2/SP-3 must pass before QE/AR integration (M3).
M2 MD-7 needs SP-3. QC gates (M1) precede any src/ code per NFR-01/02.