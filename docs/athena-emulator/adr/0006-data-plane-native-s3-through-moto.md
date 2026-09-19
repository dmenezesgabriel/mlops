# ADR-0006 — Data plane: Trino native S3 filesystem → moto S3

- Status: Accepted (spike-gated)
- Date: 2026-09-19

## Context

Query data (CTAS outputs, INSERT/UNLOAD manifests, engine temp files) must be
read/written on S3. moto serves S3 at `http://moto:5000`. Trino's S3 support
uses the native filesystem since newer versions (`fs.s3.enabled=true`,
`s3.endpoint`, `s3.region`, `s3.path-style-access=true`, static access keys;
the legacy `hive.s3.*` properties were **removed** — trino.io
`object-storage/file-system-s3.html`). Trino documents S3-compatibility
testing only against real AWS S3 and MinIO — moto's S3 is not an officially
tested target, so compatibility is unproven.

We measured the same class of concern in awswrangler parity for LocalStack:
athena requires the emulator to append `.csv` to `OutputLocation` for
wrangler's file reads (LocalStack reference, docs.localstack.cloud).

## Decision

- Trino's `hive` catalog uses the **native S3 client**:
  `fs.s3.enabled=true`, `s3.endpoint=http://moto:5000`, `s3.region=us-east-1`,
  `s3.path-style-access=true`, static creds `test`/`test`.
- The emulator **writes result artifacts itself via boto3/moto S3** (ADR-0007)
  rather than relying on the engine for artifact placement and formatting —
  guaranteeing wrangler-shaped files regardless of Trino S3 client quirks.
- This link is **spike-gated**: milestone M0 must prove (a) CTAS partition
  writes land on moto S3 and (b) `SELECT` results are readable — before any
  consumer suites are built. If moto S3 fundamentally breaks Trino (hard
  errors, silent corruption), revisit the store choice — do **not**
  pre-emptively swap to MinIO.

## Consequences

- Real engine reads/writes against the emulated bucket give end-to-end
  fidelity (partitioned CTAS + `read_sql_query` round-trips).
- Two S3-client codepaths exist (Trino's + emulator's boto3) — the emulator's
  is the source of truth for artifacts.
- Spike evidence must be captured in the backlog before M3 integration.