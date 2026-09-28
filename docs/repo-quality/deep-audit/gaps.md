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
| G-01 | mlops-shared | evaluation.py:84-85 | D1 | S1 | `calculate([1]*3,[1]*3).r2==0.0`; sklearn `r2_score` → 1.0 perfect / 0.0 wrong — impl returns 0.0 for both, perfect vs garbage indistinguishable; consumed observability-only (mlflow metrics, monitor report) | `_r2`: when `tss==0` return `1.0` if `rss==0` else `0.0` (sklearn force_finite convention) | shipped |
| G-02 | mlops-shared | logging.py:21,28-34 | D1 | S3 | `extra={"level":"SPOOFED","timestamp":"1970"}` on an ERROR record → output JSON carries spoofed `level`/`timestamp`; extras not filtered against reserved payload keys | `_extra_context`: exclude reserved payload field names | open |
| G-03 | mlops-shared | logging.py:33,36-37 | D1 | S3 | `extra={"run_id": object()}` absent from output — silent drop | `_extra_context`/`_is_json_scalar`: `str(value)` fallback for non-scalars | open |
| G-04 | mlops-shared | paths.py:14-19 | D8/D1 | S3 | `RepositoryPathResolver(/tmp/au01/repo).resolve("../../etc")` → `/tmp/etc` — escapes root; contract says repository-relative; trust boundary is repo-committed config (author error, not attacker input) | `resolve`: reject or flag non-contained results (`is_relative_to`), or document escape-by-design | open |
| G-05 | mlops-shared | paths.py:16-17 | D1 | S3 | `resolve("/a/../b")` → `/a/../b` unnormalized; relative branch resolves, absolute doesn't | `resolve`: `.resolve()` both branches | open |
| G-06 | mlops-shared | config.py:19-20 | D1 | S3 | `{1: .., "1": ..}` → `{"1": "string"}` silent collision; `on:`/`true:` YAML-1.1 keys → `"True"` | `load`: reject non-str keys instead of coercing (or detect collisions) | open |
| G-07 | mlops-shared | pipeline.py:43 | D1 | S3 | step whose `name` raises → RuntimeError propagates with zero log lines; started/failed pair broken | `run`: hoist `name` read or wrap the started-log line | open |
| G-08 | mlops-shared | datasets.py:8-27 | D4 | S3 | grep: 0 implementers/consumers repo-wide; speculative protocol surface (prior QF-6 vulture triage judged params "interface contract" — vulture disposition, not a design verdict) | delete module, or keep with documented extension-point reason at triage | open |
| G-09 | mlops-shared | pipeline.py:32 | D4 | S3 | grep: 0 consumer subclasses (`videos` uses own port; scaffold template doesn't subclass) — only the test spy exercises it | delete `PipelineStep`, or keep with documented extension-point reason at triage | open |
| G-10 | mlops-shared | tests/unit/* | D9 | S4 | mutants survived: `1 - rss/tss`→`rss/tss` (r2 unasserted), `>`→`>=` boundary; uncovered: evaluation.py:26-27,85 · logging.py:20,48-50 · paths.py:17,23 · pipeline.py:46-50 | assert `r2`/`require_within` boundary; cover `configure`, step-failure, absolute-path, exc_info branches | open |

## Triage

Rows are dispositioned at each milestone's remediation step; `shipped` and
`waived` rows stay as evidence (a waiver is a scoped decision, not silence).

| Row | Disposition | Item | Reason / note |
|---|---|---|---|
| G-01 | shipped | AF-01 | sklearn force_finite convention adopted 2026-09-28; regression tests cover both `tss==0` branches |
