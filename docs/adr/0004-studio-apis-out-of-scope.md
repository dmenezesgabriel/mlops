# ADR-0004 — Athena Studio / notebook / session / calculation APIs out of scope (shaped errors)

- Status: Accepted (user decision)
- Date: 2026-09-19

## Context

The Athena 2017-05-18 model ships 70 operations
(`research_repos/aws-cli/awscli/botocore/data/athena/2017-05-18/service-2.json`)
including Studio-era operations: `CreateNotebook`, `GetNotebookMetadata`,
`ListNotebookMetadata`, `ImportNotebook`, `ExportNotebook`,
`DeleteNotebook`, `UpdateNotebook`, `CreatePresignedNotebookUrl`,
`CreateSession`, `GetSession`, `GetSessionStatus`, `ListSessions`,
`TerminateSession`, `StartCalculationExecution`, `GetCalculationExecution`,
`GetCalculationExecutionCode`, `GetCalculationExecutionStatus`,
`StopCalculationExecution`, `ListCalculationExecutions`, `ListNotebookSessions`,
capacity ops (`CreateCapacityReservation`, `GetCapacityReservation`,
`ListCapacityReservations`, `DeleteCapacityReservation`,
`UpdateCapacityReservation`, `GetCapacityAssignmentConfiguration`,
`PutCapacityAssignmentConfiguration`, `CancelCapacityReservation`),
`ListExecutors`, `GetResourceDashboard`, `ListApplicationDPUSizes`,
`ListEngineVersions`.

None of the five target consumers depend on the Studio/notebook/session/
calculation subset: awswrangler touches only query + metadata + workgroup ops
(see PRD evidence refs); AWS CLI `examples/athena/` covers the same control/
query surface; terraform-provider-aws resources are `aws_athena_database`,
`aws_athena_workgroup`, `aws_athena_named_query`, `aws_athena_data_catalog`,
`aws_athena_prepared_statement`.

## Decision

- v1 implements the control-plane + query-plane operations only.
- Every out-of-scope operation is **present in the dispatcher** and returns a
  correctly-shaped exception — `InvalidRequestException` (400) with a message
  naming the operation and stating it is unsupported in the local emulator —
  never a 404/405/501 that would break botocore error parsing
  (ADR-0008).
- `ListEngineVersions` IS in scope (returns the pinned engine version list) —
  wrangler/cli callers expect it.

## Consequences

- Consumers that touch Studio APIs fail loudly and clearly, not silently.
- Excludes `ListExecutors`/capacity/session/notebook/calculation from v1 test
  matrix (backlog keeps a negative-test item for shaped errors).