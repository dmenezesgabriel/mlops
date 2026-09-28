# ADR-0005 — Test-quality standard (AAA unit + pytest-bdd integration)

- Status: Accepted
- Date: 2026-09-26

## Context

Coverage floors prove lines ran, not that behavior is checked (QH-3 caught a
mis-scoped floor hiding 0%-files; QH-5 reached 100% with real assertions).
Two distinct layers must both be verified per package: unit tests and
integration tests.

## Decision

- **Unit tests**: pytest, AAA shape (a reader can point at Arrange / Act /
  Assert), named fake *classes* at external I/O boundaries (not ad-hoc
  `MagicMock` webs), F.I.R.S.T., and assertion strength — a mutation
  spot-check per core module (flip a branch → some test must fail).
- **Integration tests**: pytest-bdd scenarios over user-facing surfaces —
  CLI commands, service endpoints, pipeline runs — against real or
  production-like dependencies at exactly the seams the unit tests fake.
- Test code obeys the same rules as source: typed, <500-line files,
  complexity-clean helpers (the QH-5 `test_tuning.py` C14 fix showed assert
  blocks count toward radon CC).
- A public surface with no bdd scenario is an S4 gap; a core module whose
  tests fail the mutation check is an S4 gap.

## Consequences

- "Completely covered with tests" becomes checkable, not aspirational.
- AX-2's surface→scenario matrix gives bdd coverage a shape per package.
