# ADR-0002 — Audits are read-only; every fix is its own item

- Status: Accepted
- Date: 2026-09-26

## Context

An audit session that edits source produces an unreviewable diff — report,
harness scaffolding, and behavior changes in one commit — and couples
"understand the package" with "change the package". It also tempts the
auditor to fix before finishing the measurement pass, hiding the very
evidence the fix was justified by.

## Decision

- An `AU-*` audit session may touch only `docs/repo-quality/deep-audit/`
  (the `AU-NN` report + `gaps.md` rows + checked boxes). `src/` and
  `tests/` stay untouched.
- Every confirmed finding is promoted to an `AF-*` fix item at the
  milestone's remediation step (S1 items preempt the audit sequence).
- Scratch harnesses an audit needs (microbenchmarks, stress scripts) are
  either thrown away or, when worth keeping, committed as tests inside the
  `AF-*` fix that uses them — never as part of the audit diff.

## Consequences

- Audit diffs are pure documentation — trivially reviewable.
- Fixes arrive with their evidence already filed, and each gets a dedicated
  TDD session with gates green.
- Audit reports may note "likely fix" surfaces; the fix itself decides.
