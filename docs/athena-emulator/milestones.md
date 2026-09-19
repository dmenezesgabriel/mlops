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
5. PC-1: FastAPI `POST /` catch-all + health; empty dispatch (all 70 targets →
   shaped `InvalidRequestException`) with PC-3 error serializer; first
   end-to-end test: botocore stub call to `:5001` parses error.

Exit: `make quality` green from a fresh checkout; repo pre-commit green;
stub-driven smoke test passes (botocore stub → JSON-1.1 error round-trip).

## M2 — Control-plane & metadata API (MD-*)

Steps (each TDD):
1. MD-1 workgroups (incl. `primary` default, `UpdateWorkGroup`) —
   wrangler-config parity test using `_get_workgroup_config`
   (`awswrangler/athena/_utils.py:158-187`).
2. MD-2 named queries (+ pagination), MD-3 prepared statements (RNFE policy
   per `awswrangler/athena/_statements.py:26-29`), MD-4 data catalogs,
   MD-5 engine versions, MD-6 tags.
3. MD-7 catalog read proxy to moto Glue (needs M0 SP-3 proven); parity test:
   AT data create via CLI then `list_table_metadata` returns the same table.
4. BDD features for each flow (`tests/bdd/`).

Exit: metadata ops green against botocore stubs AND awswrangler config path;
CLI `athena list-*` examples pass.

## M3 — Query engine + artifacts (QE-*, AR-*)

Steps:
1. QE-1 `trino_client.py` (statement POST / poll / DEL). Test with fake
   transport (F.I.R.S.T., no docker needed in unit tests).
2. QE-2 async executor + state registry (ADR-0009). Unit tests: state
   transitions, pre-finish `GetQueryResults` 400 text parity.
3. QE-3 ops (`Start/Stop/Get/BatchGet/GetResults/GetRuntimeStatistics`),
   QE-4 statement classification, QE-5 error mapping.
   - Regression anchor: wrangler's bad-SQL expectations
     (`awswrangler/athena/_utils.py:888-898`).
4. AR-1..4 artifact writers + OutputLocation semantics + inline pagination.
   - Contract tests: files byte-compare to wrangler expectations (QUOTE_ALL,
     headerless CSV; tab TXT; manifest → `.metadata` via `.replace` at
     `awswrangler/athena/_read.py:153`).
5. Integration: docker stack, `SELECT` via wrangler end-to-end (M0 config).

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