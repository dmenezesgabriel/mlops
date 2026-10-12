# ADR-0009 — Async query-execution state machine

- Status: Accepted
- Date: 2026-09-19

## Context

Athena's `QueryExecutionState` is `QUEUED → RUNNING → SUCCEEDED | FAILED |
CANCELLED` (enum in `service-2.json` — see README evidence index).
Consumers drive this machine:

- awswrangler polls `GetQueryExecution` every 1.0 s until a terminal state
  (`_QUERY_FINAL_STATES = ["FAILED", "SUCCEEDED", "CANCELLED"]` at
  `research_repos/aws-sdk-pandas/awswrangler/athena/_utils.py:41-42`);
  cache reads `batch_get_query_execution`
  (`awswrangler/athena/_cache.py:36-45`).
- `GetQueryResults` asked before completion gets a real-Athena 400
  `InvalidRequestException` `"Query has not yet finished. Current state:
  QUEUED|RUNNING"` (verified against AWS behavior; see ADR-0008).
- `StopQueryExecution` sets `CANCELLED`; STS-backed cancel in Trino = `DELETE`
  on the statement (trino.io client-protocol).

## Decision

1. Every query execution is an **asyncio task** recorded in the in-memory
   registry (ADR-0003): initial `QUEUED`, then `RUNNING` once dispatched to
   Trino, terminal on completion.
2. `start_query_execution` is synchronous (returns immediately with the
   execution ID) — matching Athena and wrangler's poll loop.
3. `get_query_execution`/\`batch_get_query_execution` are always answerable;
   `get_query_results` (inline) raises the exact `InvalidRequestException`
   400 while not terminal (per ADR-0008) — the failure mode consumers expect.
4. Terminal transition only after artifacts are persisted (ADR-0007), so
   consumers never see `SUCCEEDED` without readable files.
5. `stop_query_execution` → `DELETE` the Trino statement; terminal `CANCELLED`;
   `GetQueryRuntimeStatistics` returns the recorded counters (data scanned,
   engine execution time) from the task.

## Consequences

- Wrangler's tight 1 s poll and cache flow work unmodified.
- Concurrency is bounded by an asyncio semaphore (config) — bounded, not
  unlimited, to protect the dev machine.
- Emulator restarts lose running executions (ADR-0003) — they surface as
  `ResourceNotFoundException` on follow-up reads, matching a dead emulator.