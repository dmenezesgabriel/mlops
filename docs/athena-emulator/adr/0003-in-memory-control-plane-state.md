# ADR-0003 — Control-plane state is in-memory only

- Status: Accepted (user decision)
- Date: 2026-09-19

## Context

Workgroups, named queries, prepared statements, data catalogs, and query
executions are stateful resources. Persistent options (DynamoDB, S3 JSON,
SQLite inside the container) add machinery with no consumer benefit: none of
the five target consumers require durability across emulator restarts, and the
reference behavior (moto) is itself in-memory (registries live in
`research_repos/moto/moto/athena/models.py` as Python dicts).

## Decision

- All control-plane registries are in-memory Python structures owned by
  `state.py`.
- No persistence layer in v1; data is lost when the `athena` container stops
  — documented user-facing behavior.
- Query executions are in-memory task records too (ADR-0009); result
  *artifacts* still land in moto S3 so S3-side data survives (ADR-0007).

## Consequences

- Simple, race-free (single process) and fast to reset in tests.
- Multi-replica / HA is explicitly out of scope v1.
- `ListQueryExecutions` returns only the current process's executions — same
  class of behavior moto has.