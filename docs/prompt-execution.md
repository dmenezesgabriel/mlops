# Execution session protocol (OPERATIONAL)

> **Operational session protocol.** How an execution session runs in this
> repo. It references the permanent docs and the ephemeral working docs;
> like all planning docs, its content is never cited in code — only the
> permanent docs (`architecture/`, `adr/`, `methodology/`, `components/`)
> and `file:line` evidence may be.

Target: the package/component named by the current backlog item. Doc index:
`docs/README.md` (doc map + verified evidence index). Closed-workstream
history: `docs/archive/`.

## Prompt → this repo (file map)

| Generic slot | This repo's file |
|---|---|
| `docs/backlog.md` | `docs/backlog.md` — one evidence-anchored item per row, ID-prefixed per section |
| `docs/slices/SL-NNN-*.md` | `docs/prd.md` — per-domain FR tables with evidence + acceptance |
| `docs/research/*.md` | `docs/architecture/*.md` risk sections + `docs/adr/` spike gates |
| `docs/adr/*.md` | `docs/adr/NNNN-*.md` (architecture decisions) + `docs/methodology/*/adr/` (process decisions) |
| evidence files | `docs/audits/` (audit reports backing the register) |
| gap register | `docs/gaps.md` — measured findings only |

## 1. Orient — grep first, read only what you need

1. `git log --oneline -15` and `git status --short` — uncommitted work means
   the previous session stopped mid-item; understand it before starting.
2. Read `docs/README.md` (doc map + evidence index) and the item's
   component doc under `docs/architecture/` / `docs/components/` if not
   already known.
3. Next item: `grep -n "^## M" docs/milestones.md` for the current
   milestone → its steps → `grep -n "<ID>" docs/backlog.md`. Pending S1
   fix items preempt the sequence.
4. Read the item's **Evidence** cell (`file:line` into the codebase,
   `research_repos/…`, or upstream docs) and each ADR it cites.
5. Follow `AGENTS.md` (behavior, code style, TDD, dependency wrapping,
   host-resource rules). Do the searches yourself.

## 2. Scope — one item per session

- Do **one backlog item (or milestone step)** per session, then stop; the
  next session takes the next. If an item is still too big, split it in
  `docs/backlog.md` first (new sub-item with its own evidence), then do the
  first piece.
- Finish what was started: don't open a new item while one is un-checked.
- Never cut the stack horizontally: a slice closes only when its consumer
  path runs end-to-end.
- Audit (`AU-*`) and fix (`AF-*`) items have their own procedures —
  appendix B.

## 3. PRD handling

- `prd.md` holds per-domain FR tables. **Do not rewrite it per item.**
- For a **new capability** add a row with: (a) *who else implements it* —
  which reference (code, checkout, upstream docs) has it, read not assumed;
  (b) *implementation inventory* — the exact `file:line` paths to read,
  grouped by concern; where references disagree, name the disagreement —
  it is the decision the item must make; (c) *gap analysis* — ours vs the
  references: absent / partial / complete.
- Verify every cited path on disk in the session that writes it. Cite
  symbols and paths; one fact per table row; no hard-wrapped prose.

## 4. Build — strict TDD, evidence over assumption

- Before writing code, read the references named in the Evidence cell and
  take the best of them. Act on what you measured, never on assumption.
- Test-driven development on application source, strictly: RED → GREEN →
  REFACTOR. Every new/refactored piece gets unit tests; integration tests
  run against the real dependency where the unit boundary would fake the
  link under test.
- Test the program and its integrations with production dependencies.
  Don't test conventions.
- Constraints (AGENTS.md): no `any`/`Dict`; functions 4–20 lines; files
  < 500 lines; early returns, no `else`; wrap third-party libs behind
  project-owned thin interfaces.
- `research_repos/` is read-only; never import/link/vendor it. Official
  packages only; guard against supply-chain attacks.
- No workarounds, no band-aids; if a spike-gated risk hard-fails, **stop
  and report** — do not invent a workaround.
- A defect you introduce is yours to fix before stopping, planned or not.
- Host-resource rules (AGENTS.md): measure before heavy commands, cap
  parallelism at half of `nproc`, one heavy command at a time, stop what
  you start.

## 5. Validate like the auditor would

- Numbers over adjectives: quote measurements, `file:line`, coverage %.
- A "race-free" claim needs stress evidence or a by-construction argument;
  a "no leak" claim needs a tracemalloc diff or a bounded-growth argument —
  never vibes.
- Treat a suspect as innocent until measured: reports may list suspects;
  registers only list measured findings.
- Reuse running instances; don't start duplicates — probe ports first.
  Treat the local stack's data as the user's: read-only during validation;
  throwaway resources for writes.

## 6. Close the step

- Run the package's full gate and put the numbers in the **commit body**,
  never in a doc (`make quality`; see `AGENTS.md` heavy-command rules).
- Commit each step with a conventional commit (`feat:`, `fix:`, `test:`,
  `docs:`).
- Update the working docs by **editing** them — one line per item, no
  appended corrections, no dated blocks: check the box in `backlog.md` and
  the milestone step in `milestones.md`; disposition rows in `gaps.md`.
- Closes a risk: mark it handled in the owning `architecture/*.md` risk
  section.
- Code comments state their fact so it stands alone; they may cite an ADR
  or a canonical model path, never a milestone/backlog/PRD ID.
- Stop, and report: what shipped, what you measured, what the next item is.

## Appendix A — athena-local items

Domain: `libs/athena-local` — Athena emulator, Trino + moto, JSON-1.1 parity
for boto3 / awswrangler / AWS CLI / terraform. arc42:
`architecture/athena-local.md`; decisions: `adr/0001…0013`.

- Canonical wire contract: `research_repos/aws-cli/awscli/botocore/data/
  athena/2017-05-18/service-2.json` — byte-identical to the installed
  botocore model; single source of truth for the 70 ops.
- Boundaries (ADR-0008): `trino_client.py` / `glue_proxy.py` /
  `s3_writer.py` are the only modules touching third-party services; no
  moto internals reuse.
- Consumer-shaped validation (the "human" is each consumer): botocore
  70-op parity loop, awswrangler `read_sql_query`/cache/CTAS/prepared
  statements, AWS CLI `athena` examples via `--endpoint-url`, terraform
  op-shape parity. Evidence anchors: `docs/README.md` evidence index.
- Probe before measuring: `curl -s http://localhost:5001/health`,
  `ss -ltnp | grep -E ':(5000|5001|8080)'`. A stale `athena`/`trino`
  container invalidates timing and log checks — verify its start time.
- Compose services persist after the session that started them — `docker
  compose stop` when done (idle Trino alone held ~2 GB, measured
  2026-10-10).
- Recorded parity deltas are in `projects/athena_emulator/PARITY.md`; the
  closed workstream set (M0–M7, GF/QA items) is at
  `docs/archive/athena-emulator/`.

## Appendix B — audit items (`AU-*` / `AF-*` / `AX-*`)

Rubric: `docs/methodology/deep-audit/methodology.md` (procedure §3,
dimensions D1–D10 §4, severity §5, measurement standards §6, report
template §7). Its decisions: `docs/methodology/deep-audit/adr/`.

- An `AU-*` audit is read-only on `src/` — its diff touches only `docs/`
  (report + gap rows + checked boxes). Never fix inside an audit session
  (methodology ADR-0002).
- Reports land at `docs/audits/AU-NN-<slug>.md`; confirmed findings promote
  to `docs/gaps.md` (sequential `G-NN` — next free number repo-wide).
- An `AF-*` fix is its own session: a failing test demonstrating the harm
  before touching source → GREEN → gates → commit. No weakening gates, no
  `type: ignore`/noqa/pragma to silence a finding, no test deletions to
  make a floor pass — escalate instead.
- The completed 2026 run (27 package audits, 2 sweeps, 324 dispositioned
  gaps) is archived at `docs/archive/repo-quality/deep-audit/`.
