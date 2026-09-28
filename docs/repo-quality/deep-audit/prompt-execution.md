# Execution session protocol — Repo Deep Audit (OPERATIONAL)

> **Operational session protocol.** How an execution session runs for this
> workstream. References permanent docs (`methodology.md`, `adr/`) and
> ephemeral working docs; like all planning docs, its content is never cited
> in code — only the permanent docs and `file:line` evidence may be.

Target: every workspace package (inventory + order:
`docs/repo-quality/deep-audit/README.md`). Rubric:
`docs/repo-quality/deep-audit/methodology.md`. Parent workstream:
`docs/repo-quality/` (gate parity — complete; those gates are the floor this
audit verifies code actually deserves).

## Prompt → this repo (file map)

| Generic slot | This repo's file |
|---|---|
| `docs/backlog.md` | `docs/repo-quality/deep-audit/backlog.md` — `AU-*` audits, `AF-*` fixes, `AX-*` cross-cutting |
| `docs/slices/SL-NNN-*.md` | `docs/repo-quality/deep-audit/prd.md` — FR-A-01…FR-A-12 |
| `docs/research/*.md` | `docs/repo-quality/deep-audit/methodology.md` §4 rubric + §8 risk table; README "Known risk seeds" |
| `docs/adr/*.md` | `docs/repo-quality/deep-audit/adr/0001…0005` — methodology decisions |
| slice evidence files | `docs/repo-quality/deep-audit/audits/AU-NN-<slug>.md` — one report per audit |
| gap register | `docs/repo-quality/deep-audit/gaps.md` |

## 1. Orient

1. `git log --oneline -15` and `git status --short` — uncommitted work means
   the previous session stopped mid-item.
2. Read `docs/repo-quality/deep-audit/README.md` (inventory + seeds) and
   `methodology.md` §4 if not already known.
3. Next item: `grep -n "MA-[0-9]" docs/repo-quality/deep-audit/milestones.md`
   for the current milestone → its steps → `grep -n "<ID>" …/backlog.md`.
   Pending `AF-*` S1 items preempt the audit sequence.
4. For an `AU-*` item, read the target package's README/pyproject and the
   inventory row's "Depends on" — audits downstream of a dependency already
   audited may reuse its report's contract verdicts.
5. Follow `AGENTS.md` rules throughout (typing, size limits, named fakes).

## 2. Scope — one item per session

- Do **one backlog item** per session, then stop. An `AU-*` audit is
  read-only on `src/` — its diff may touch only `docs/` (report + gap rows +
  checked boxes). If the item is still too big, split it in `backlog.md`
  first (new sub-item, own evidence), then do the first piece.
- An `AF-*` fix is its own session: RED test demonstrating the gap → GREEN →
  gates → commit. Never fix inside an audit session (ADR-0002).
- Finish what was started: don't open a new item while one is un-checked.
- `AX-*` sweeps run only after their triggering audits complete (see
  `backlog.md` section C).

## 3. Audit session procedure (per methodology §3)

1. Surface inventory + entry points (grep + `radon raw`).
2. Callgraph walk from every public entry point; record the trace.
3. Dimension walk D1…D10 — flag suspects `file:line`.
4. Measure every suspect that would carry severity: `timeit` scaling,
   `tracemalloc`, thread-stress, exploit-shaped test, mutation check — per
   §6. Unmeasured suspects stay in the report, not the register.
5. Write `audits/AU-NN-<slug>.md` from the §7 template; promote confirmed
   findings into `gaps.md` (ID `G-NN`, severity, candidate fix surface).
6. Check the backlog/milestone boxes; commit docs-only
   (`docs(deep-audit): audit <pkg> — N gaps (S1×a, S2×b, …)`).

## 4. Fix session procedure (`AF-*`)

- Evidence cell names the gap row; reproduce first — a failing test that
  demonstrates the harm before touching source.
- No weakening gates, no `type: ignore`/noqa/pragma to silence a finding,
  no test deletions to make a floor pass — escalate instead.
- Perf fixes keep the audit's benchmark harness and report before/after
  numbers in the commit body.
- On green: edit the gap row to `shipped`, check the `AF-*` box, commit with
  the gate numbers in the body.

## 5. Validate like the auditor would

- Numbers over adjectives: quote measurements, `file:line`, coverage %.
- A "race-free" claim needs the §6 evidence (stress harness or
  single-threaded-by-construction argument); a "no leak" claim needs a
  tracemalloc diff or a bounded-growth argument — never vibes.
- Treat a suspect as innocent until measured: reports may list suspects;
  registers only list measured findings.
- Careful with shared state: don't mutate `audits/` rows of other items;
  gap IDs are sequential (`G-NN`) — take the next free number.

## 6. Close the step

- Update docs by **editing**: check boxes in `backlog.md`/`milestones.md`,
  disposition rows in `gaps.md`. No appended correction blocks.
- If an audit discovers the methodology is wrong (a useless dimension, a
  missing check), fix `methodology.md` + note in the report — don't fork
  local conventions.
- Stop and report: what was audited, what was measured, what shipped, what
  the next item is.
