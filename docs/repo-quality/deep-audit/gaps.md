# Gap register — Repo Deep Audit (EPHEMERAL)

> **EPHEMERAL WORK REGISTER — iterates freely; never cited from code.**
> One row per *measured* finding: the evidence, the severity, and a candidate
> fix surface so each fix lands as a small step. `AU-*` audits append rows;
> each milestone's remediation step promotes rows to `AF-*` backlog items
> (or waives them with a written reason). A row leaves the register when its
> fix ships or is waived.
>
> A suspect without a measurement lives in its `audits/AU-NN-*.md` report —
> it does not get a row here until it carries a number or a failing test
> (ADR-0001). Severities: S1 defect/vuln/race (fix before next audit) ·
> S2 measured perf/memory risk · S3 type/design/clarity debt · S4 test gap.

| ID | Pkg | File:line | Dim | Severity | Measured evidence | Candidate fix surface | Status |
|---|---|---|---|---|---|---|---|
| *(register empty — first rows land with AU-01)* | | | | | | | |

## Triage

Rows are dispositioned at each milestone's remediation step; `shipped` and
`waived` rows stay as evidence (a waiver is a scoped decision, not silence).

| Row | Disposition | Item | Reason / note |
|---|---|---|---|
| *(empty)* | | | |
