# Milestones — repo-wide quality-gate parity (EPHEMERAL)

> **EPHEMERAL WORK PLAN — iterates freely; never cited from code.**
> Ordered phases; each step lands green under `make quality`.
> Items live in `backlog.md` (`QG-*` gate wiring, `QF-*` finding fixes).

## MQ-0 — Audit: measure the gap (this plan's evidence)

Full-signature gate audit of the uv monorepo (2026-09-27): every package's
Makefile walked, root `PACKAGES`/pre-commit/import-linter coverage diffed
against the athena §8.4 gate set, and each missing tool run live to size
its findings:

1. [x] Inventory per-package Makefile targets vs the ten-gate standard.
2. [x] Run radon/xenon/vulture/bandit/deptry where not wired; record
   measured findings per package in `backlog.md` evidence cells.
3. [x] Prove the shared radon recipe is a silent no-op
   (`-x "*/node_modules/*"` binds `--max`, not `--exclude`; `-e` verified
   to exclude katex while still reporting real C+).
4. [x] Bootstrap this doc set (`QG-1`).

Exit: `backlog.md` rows carry measured evidence; no unmeasured item.

## MQ-1 — Gate wiring: every package exposes every gate

1. [x] `QG-2` radon recipe fix — **sequenced with its findings** (see
   constraint): `QF-1`/`QF-2`/`QF-3`/`QF-9` fixes land first or in the
   same commit so `make complexity` stays green.
2. [x] `QG-3`/`QG-4` `sagemaker-local` + `sagemaker_*` ×4 gain
   coverage/complexity/dependencies/security/maintainability targets.
3. [x] `QG-5` root `PACKAGES` += `ml_specialization` + `sagemaker_*`;
   root `quality` chain += `maintainability`.
4. [x] `QG-6`/`QG-7` bandit+vulture join every `security` target; xenon
   `maintainability` target per package.
5. [x] `QG-8` import-linter: `glue_overlay` root + missing contracts.
6. [x] `QG-9` pre-commit: extend bandit/vulture/xenon past
   `libs/athena-local/`.

Exit: `make -C <pkg> quality` runs all ten gates for every workspace
package; a deliberately C+ function fails `complexity`/`maintainability`
(no-op regression probe).

## MQ-2 — Findings: clear what the gates flag

Worst-first ordering; each row's evidence cell names file:line and the
measured rank/count. Fixes are real refactors — no `# noqa`/`nosec`-spam;
a configured-out finding carries its reason in the backlog row.

1. [x] `QF-1` `videos-linter` `linter_service.py` (D25 — worst measured).
2. [x] `QF-2` `athena-local` tests (~12 C+/D/E functions — whole-package
   scope decision created these).
3. [x] `QF-3` `videos` (ManimRenderer C11, module-B ×2, vulture 3@80).
4. [x] `QF-4` `nyc_taxi_demand_forecasting` (module-B `train.py`,
   `monitor.py`).
5. [x] `QF-5`…`QF-9` remaining single-finding packages.
6. [x] `QF-10` verify-clean row re-measured after wiring.

Exit: `make quality` green over the expanded `PACKAGES` with every gate
functional.

## MQ-3 — Hardening (user-approved stretch)

1. [ ] Coverage floors: measure current % per package, wire
   `--cov-fail-under` ratchets (target ≥75 matching athena; a package
   below floor gets a test-coverage sub-item or a documented floor with
   reason — no silent waivers).
2. [ ] Pyright `standard`→`strict` per lib, athena QA-6 playbook (its
   flip cost 72 errors / 33 kLOC); root pyproject stays `standard`.

Exit: floors and strictness ratcheted where measured feasible; the doc
set closes or hands residual items back to `backlog.md`.

## Sequence & dependencies

```
MQ-0 (audit) → MQ-1 (wiring) → MQ-2 (findings) → MQ-3 (floors/strictness)
```

Constraint: a gate flip never commits ahead of the fixes it requires —
`make quality` stays green at every commit (per-package flip+fix in one
commit is the preferred shape).
