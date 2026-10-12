# ADR-0011 — Managed-results workgroups skip S3 artifacts

- Status: Accepted
- Date: 2026-09-22

## Context

A workgroup with `ManagedQueryResultsConfiguration.Enabled=true` stores its
query results in Athena-owned storage, which consumers cannot reference. The
canonical service model makes the wire contract explicit: *"A workgroup
cannot have the `ResultConfiguration$OutputLocation` parameter when you set
this field to true"* (botocore `athena/2017-05-18/service-2.json`,
`ManagedQueryResultsConfiguration` shape), and awswrangler's managed path
sends `StartQueryExecution` with **no** `ResultConfiguration` at all
(`awswrangler/athena/_utils.py:105-109`), then reads the rows inline via
`GetQueryResults` whenever `OutputLocation` is absent
(`awswrangler/athena/_read.py:450,928`). Its managed tests assert
`query_metadata["ResultConfiguration"].get("OutputLocation") is None`
(`awswrangler/tests/unit/test_athena.py:125`).

moto has no managed-results support: its Athena workgroup model holds only
`ResultConfiguration` (`research_repos/moto/moto/athena/models.py:51`) and
its stub merely appends `{id}.csv` to a folder location (`:137-140`).

ADR-0009 #4 requires the artifact writer to persist files before the
SUCCEEDED transition — for executions whose results are written to a
consumer-visible `OutputLocation`. A managed execution has no such location,
so that rule cannot and need not hold.

## Decision

1. A managed workgroup (`ManagedQueryResultsConfiguration.Enabled=true`)
   resolves no `OutputLocation` at all: `StartQueryExecution` without a
   request `ResultConfiguration` no longer 400s, the execution stores an
   empty `ResultConfiguration()`, and a request-carried `OutputLocation` on a
   managed workgroup is ignored (the model forbids the combination).
2. `GetQueryExecution` for a managed execution reports the `ResultConfiguration`
   member **without** `OutputLocation` — matching real Athena and wrangler's
   managed assertion.
3. The executor skips the artifact writer for managed records (`QueryExecutionRecord.managed_results`)
   yet still transitions to `SUCCEEDED`; the terminal rows are cached and
   served inline via `GetQueryResults`, wrangler's managed read path.
4. This is a carve-out to ADR-0009 #4, scoped strictly to managed records:
   non-managed executions keep writer-before-SUCCEEDED ordering.

## Consequences

- wrangler's managed workgroup-config and api-read paths run against the
  emulator with zero wrangler configuration.
- Managed executions leave no objects in moto S3, mirroring Athena-owned
  storage as seen by consumers.
- Consumers that read `GetQueryExecution.ResultConfiguration.OutputLocation`
  for a managed execution see the member absent — the shape wrangler asserts.