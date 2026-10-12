# ADR-0010 — `{QueryID}.csv` carries the quoted header row as line 1

- Status: Accepted
- Date: 2026-09-21
- Supersedes: the "headerless CSV" descriptor in ADR-0007 (Context CSV/DML
  bullet and Decision item 1, `SELECT` → csv row) — and only that descriptor.
  Every other ADR-0007 decision remains in force.

## Context

ADR-0007 described the DML CSV artifact as **headerless**. That was wrong.
awswrangler's `_fetch_csv_result` reads the file with

```
s3.read_csv(
    path=[path],
    dtype=query_metadata.dtype,
    parse_dates=query_metadata.parse_timestamps,
    converters=query_metadata.converters,
    quoting=csv.QUOTE_ALL,
    keep_default_na=False,
    na_values=["", "NaN"],
    skip_blank_lines=False,
    ...
)
```

(`research_repos/aws-sdk-pandas/awswrangler/athena/_read.py:225-238`) — no
`names=` and no `header=None`. `query_metadata.dtype` is keyed by column
**names** (built from `GetQueryResults` metadata at
`awswrangler/athena/_utils.py:_get_query_metadata`). With a headerless file,
pandas promotes the first data row to the header, so every dtype lookup misses
and every column falls back to inference.

Measured on a real query result:

```
$ head -2 6a80f17a-....csv
"person_id","name","dt"
"1","alice","2024-01-01"
```

Real Athena CSV files also start with the quoted header row (AWS docs —
`athena/latest/ug/querying-finding-output-files.html`).

## Decision

1. `{QueryID}.csv` starts with a **quoted header row** as line 1 — every cell
   quoted via `csv.QUOTE_ALL` (comma delimiter, `\n` row terminator) — so
   wrangler's `dtype`-by-name read lands on correctly named columns.
2. NULLs serialize as the empty quoted cell `""`, which wrangler's
   `na_values=["", "NaN"]` maps back to `NA`.
3. `{QueryID}.txt` (DDL/UTILITY) stays **headerless**: wrangler passes
   `names=query_metadata.dtype.keys()` explicitly for txt
   (`awswrangler/athena/_utils.py:200-213`). Unchanged from ADR-0007.
4. The `.csv.metadata` sidecar is emulator-owned JSON (columns + row count);
   nothing parses it (real Athena's is binary) and wrangler deletes it after
   reading.

## Consequences

- awswrangler `read_sql_query` infers column names and dtypes from a
  `{QueryID}.csv` result with no wrangler-side workarounds.
- AR-2's `OutputLocation`-filename semantics (ADR-0007 #2) stay: the value
  ends in `.csv`, and line 1 of that file is always the header.
- Backlog AR-1 lands the header-row writer; the emulator composes it into the
  query plane (M3 step 4) behind `main`.