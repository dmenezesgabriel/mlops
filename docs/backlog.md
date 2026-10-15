# Backlog (EPHEMERAL)

> **EPHEMERAL — iterates; never cited from code.** One work item per row,
> evidence-anchored, TDD-shaped. Group rows under a lettered section per
> workstream/domain; each section header declares its ID prefix. Prefixes
> from closed workstreams (QC/SP/PC/MD/QE/AR/CS/DP/NB/GF/QA, MQ/QH,
> AU/AF/AX, SX) live in `docs/archive/` — reuse a prefix only for the same
> domain. Work sizes: S ≤ 1 day · M = 1–3 days · L = 3–5 days.

No open items. Closed sections (archived 2026-10-14):
A. Athena emulator showcase notebooks (NB-7…16) →
`docs/archive/athena-emulator/backlog.md` §L · B. SSG site experience
(SX-1…14) → `docs/archive/ssg-site/backlog.md` · C. Fix items (AF-175) →
`docs/archive/repo-quality/deep-audit/backlog.md` §D.

## Definition of Done (all items)

- Evidence cell cites `file:line` or measured numbers — never "should".
- TDD where behavior changes: failing test first; pure refactors keep
  existing tests green.
- Gates green for the touched package (`make quality`), numbers recorded
  in the commit body.
- Item box checked in the same commit; owning milestone step updated.
