# ADR-0007 — Result artifacts and `OutputLocation` semantics

- Status: Accepted
- Date: 2026-09-19
- Note: the "headerless CSV" descriptor is superseded by
  [ADR-0010](0010-csv-header-row-and-bytes.md) — `{QueryID}.csv` **does** carry
  the quoted header row as line 1. Everything else here stands.

## Context

awswrangler is the strictest consumer and dictates artifact shapes:

- CSV / DML results: needs `OutputLocation` ending `.csv`
  (`research_repos/aws-sdk-pandas/awswrangler/athena/_read.py:209-238`) and
  reads the file with `quoting=csv.QUOTE_ALL`; the quoted header row is line 1
  (ADR-0010); deletes the sidecar `{path}.metadata` after reading.
- TXT / UTILITY results (`SHOW CREATE TABLE`, `DESCRIBE`): `.txt`,
  tab-separated, `QUOTE_ALL`, sidecar `.metadata`
  (`awswrangler/athena/_utils.py:190-221`).
- CTAS/INSERT/UNLOAD: wrangler reads `Statistics.DataManifestLocation`, i.e.
  `.../{QueryID}-manifest.csv` (one `s3://` path per line) plus `{QueryID}.metadata`
  (`awswrangler/athena/_read.py:62-81,135-206`; metadata path derived by
  `.replace("-manifest.csv", ".metadata")` at `:153`).
- Inline `GetQueryResults`: `Rows[0]` is the **header row** (wrangler strips it
  — `awswrangler/athena/_read.py:357,383`), every cell is
  `{"VarCharValue": "<string>"}`; paging via `MaxResults` and opaque
  `NextToken` (page size cap 1000 in the model).
- Real Athena writes `{QueryID}.csv` (DML), `{QueryID}.txt` (DDL/UTILITY),
  `{QueryID}-manifest.csv` (CTAS/INSERT/UNLOAD) and `.csv.metadata`/`.txt.metadata`
  sidecars under `OutputLocation` (AWS docs: `athena/latest/ug/querying-finding-output-files.html`).
- moto's own stub just appends `{id}.csv` to a folder-`OutputLocation`
  (`research_repos/moto/moto/athena/models.py:140`) — NOT a contract we copy;
  we own the semantics.

## Decision

1. `StatementType` classification drives artifacts:
   - `SELECT` → `DML` → `{QueryID}.csv` (quoted header row as line 1 — see
     ADR-0010 — QUOTE_ALL) + `.csv.metadata`.
   - `DESCRIBE`, `SHOW CREATE TABLE` → `UTILITY` → `{QueryID}.txt`
     (tab-separated, QUOTE_ALL) + `.txt.metadata`.
   - CTAS / `INSERT` / `UNLOAD` → manifest mode: `{QueryID}-manifest.csv`
     (one `s3://` path per line) + `{QueryID}.metadata`; `Statistics.DataManifestLocation`
     points at the manifest.
2. `OutputLocation` returned by `GetQueryExecution` is the **full artifact
   path** (file name included), matching real Athena and wrangler's
   `endswith(".csv")` / `(".txt")` checks.
3. Artifacts are written by `athena_local/artifacts.py` via boto3→moto S3 —
   never by relying on Trino to place/format them (ADR-0006).
4. Inline `GetQueryResults` always includes the header row as `Rows[0]`,
   respects `MaxResults` (≤1000) + opaque `NextToken`, and never duplicates
   rows between pages.
5. Supported types serialize losslessly to `VarCharValue` via Trino `data`
   cells (number/bool/date/decimals formatted like Athena; null → no
   `VarCharValue` in the cell dict, matching the model's `VarCharValue` being
   optional).

## Consequences

- awswrangler's file + API read paths work with zero wrangler config.
- Emulator owns artifact timing: files are written **before** the execution
  transitions to `SUCCEEDED`, or wrangler races missing S3 objects.
- Cache flow (`_cache.py`) reads `OutputLocation` + `DataScannedInBytes` from
  `GetQueryExecution`/`batch_get_query_execution` — both must be populated
  accurately.