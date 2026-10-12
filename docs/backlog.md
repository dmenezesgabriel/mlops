# Backlog (EPHEMERAL)

> **EPHEMERAL — iterates; never cited from code.** One work item per row,
> evidence-anchored, TDD-shaped. Group rows under a lettered section per
> workstream/domain; each section header declares its ID prefix. Prefixes
> from closed workstreams (QC/SP/PC/MD/QE/AR/CS/DP/NB/GF/QA, MQ/QH,
> AU/AF/AX) live in `docs/archive/` — reuse a prefix only for the same
> domain.

## <A>. <Domain> (<PREFIX>-*)

| ID | Item | Work | Evidence | Depends |
|---|---|---|---|---|

## Definition of Done (all items)

- Evidence cell cites `file:line` or measured numbers — never "should".
- TDD where behavior changes: failing test first; pure refactors keep
  existing tests green.
- Gates green for the touched package (`make quality`), numbers recorded
  in the commit body.
- Item box checked in the same commit; owning milestone step updated.
