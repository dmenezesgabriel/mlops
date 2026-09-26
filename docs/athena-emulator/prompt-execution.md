# Execution session protocol — Athena Local Emulator (OPERATIONAL)

> **Operational session protocol.** Describes how an execution session runs for
> this project. It references the permanent docs and the ephemeral working
> docs; like all planning docs, its content is never cited in code — only the
> ADRs/`architecture.md` and their evidence anchors may be.

Target: `libs/athena-local` — AWS Athena emulator backed by Apache Trino + moto
(S3/Glue), JSON-1.1 protocol parity for boto3 / awswrangler / AWS CLI /
terraform-provider-aws. Full context: `docs/athena-emulator/README.md` (doc map
+ **verified evidence index**), `docs/athena-emulator/architecture.md` (arc42).

## Prompt → this repo (file map)

This protocol is the project-specific form of a generic execution-session
prompt. The generic prompt's slots map here:

| Generic slot | This repo's file |
|---|---|
| `docs/backlog.md` | `docs/athena-emulator/backlog.md` — 8 workstreams, item IDs (QC-*, SP-*, PC-*, MD-*, QE-*, AR-*, CS-*, DP-*) |
| `docs/slices/SL-NNN-*.md` | `docs/athena-emulator/prd.md` — FR-01…FR-19 with evidence + acceptance rows |
| `docs/research/usability-audit.md` | `docs/athena-emulator/architecture.md` §11 (risk table) + ADR-0005/0006 (spike gates) |
| `docs/adr/0011-vertical-slices.md` | `docs/athena-emulator/milestones.md` (M0 spike → M5 hardening, ordered) |
| `docs/adr/0015…0019` (UI tokens/layout) | Not applicable — this is an API service; the "UI" is the wire protocol |
| `research_repo/` (18 repos) | `research_repos/boto3`, `research_repos/moto`, `research_repos/aws-sdk-pandas`, `research_repos/aws-cli`, `research_repos/terraform` (frozen, read-only) + installed botocore at `.venv/lib/python3.11/site-packages/botocore/data/athena/2017-05-18/service-2.json.gz` |
| `docs/architecture/cross-cutting.md` | `docs/athena-emulator/architecture.md` §8 (cross-cutting: typing, errors, logging, quality gates) |

Cross-tool contract the repo must never break (permanent evidence):
`research_repos/aws-cli/awscli/botocore/data/athena/2017-05-18/service-2.json`
(verified byte-identical to the venv botocore model — same 70 ops, same
shapes) — single source of truth for the wire protocol.

## 1. Orient — grep first, read only what you need

1. `git log --oneline -15` and `git status --short`. Uncommitted/untracked work
   means the previous session stopped partway — understand it before starting.
2. Read `docs/athena-emulator/README.md` (doc map + evidence index) and
   `docs/athena-emulator/architecture.md` §5 (modules) if not already known.
3. Find the next work item: start with `grep -n "M[0-9]" docs/athena-emulator/milestones.md`
   for the current milestone, then the milestone's steps; for a step's items,
   `grep -n "<ID>" docs/athena-emulator/backlog.md` (e.g. `QE-1`).
4. Read the item's **Evidence** cell (file:line into `research_repos/…` or
   upstream docs) and the linked ADR: `grep -rn "ADR-000N" docs/athena-emulator/`
   then read only that ADR.
5. Follow `AGENTS.md` (behavior, code style, TDD, deps wrapping) and
   `docs/athena-emulator/architecture.md` §8.4 gates. Do the searches yourself.

## 2. Scope — one item per session

- Do **one backlog item (or milestone step)** per session, then stop; the next
  session takes the next. If an item is still too big, split it in
  `docs/athena-emulator/backlog.md` first (new sub-item with its own evidence),
  then do the first piece.
- Milestones are ordered: M0 (spike) is a **hard gate** before any QE/AR
  integration (ADR-0006); M1 (gates/skeleton) before any `src/` code.
- Never cut the stack horizontally: "an API with no artifacts/consumers is not
  shipped" — a slice closes only when its consumer path (wrangler/CLI/boto3)
  runs end-to-end against the compose stack.
- Finish what was started: don't open a new workstream while the current item
  is un-checked.

## 3. PRD handling

- The PRD already exists (`docs/athena-emulator/prd.md`) and covers the planned
  scope with evidence + acceptance. **Do not rewrite it per item.**
- For a **new capability** not in FR-01…FR-19: add a row following the same
  table shape, with (a) *who else implements this* — which of the 5 research
  repos + LocalStack (validated reference) have it, read from code not
  assumes; (b) *implementation inventory* — the exact `research_repos/…:line`
  paths to read, grouped by concern (API shape, state, artifacts, errors);
  where moto and awswrangler disagree (e.g. `OutputLocation` suffixing, moto
  `models.py:140` vs wrangler `_read.py:220`) name the disagreement — it is
  the decision the item must make; (c) *gap analysis* — ours vs the
  references: absent / partial / complete. Any gap the item closes tags its
  risk entry in `architecture.md` §11.
- Verify every cited path on disk in the session that writes it. Cite symbols
  and paths; one fact per table row; no hard-wrapped prose.

## 4. Build — strict TDD, evidence over assumption

- Before writing code, read the reference implementations named in the item's
  Evidence cell (moto athena/glue models, awswrangler contracts, botocore
  model) and take the best of them. Act on what you measured, never on
  assumption. Web-search / read official docs (trino.io, AWS Athena docs)
  when references and model don't settle a fact.
- Test-driven development on application source, strictly: RED → GREEN →
  REFACTOR. Every new/refactored piece gets unit tests; integration tests run
  against the docker stack (moto + trino + athena) where the unit boundary
  would fake the link under test.
- Test the program and its integrations with its production dependencies
  (moto S3/Glue, Trino). Don't test conventions.
- Constraints (AGENTS.md + architecture §8): no moto internals reuse
  (ADR-0008); `trino_client.py` / `glue_proxy.py` / `s3_writer.py` are the
  only boundaries touching third-party services; no `any`/`Dict`; functions
  4–20 lines; files < 500 lines; early returns, no `else`.
- No workarounds, no band-aids; if a spike risk (SP-2 moto-S3, SP-3
  `GetUserDefinedFunctions`) hard-fails, **stop and report** — do not invent a
  workaround.
- Reference repos are read-only; never import/link/vendor them. Only official
  packages; guard against supply-chain attacks.
- A defect you introduce is yours to fix before stopping, planned or not.

## 5. Validate like the consumer would

- The "human" here is each of the five consumers. Run the consumer suites
  against the running stack (CS-*): botocore 70-op parity loop, awswrangler
  `read_sql_query`/cache/CTAS/prepared statements, AWS CLI `athena` examples
  via `--endpoint-url`, terraform op-shape parity (SDK Go v2 + boto3).
- Measure; don't eyeball. Record numbers: `GetQueryExecution` → `SUCCEEDED`
  latency vs wrangler's 1 s poll (`awswrangler/athena/_utils.py:41-42`),
  artifact byte-shape (headerless QUOTE_ALL CSV; tab TXT; manifest) against
  wrangler expectations (`awswrangler/athena/_read.py:209-238`,
  `_utils.py:190-221`, `_read.py:153`).
- Reuse running instances; don't start duplicates. Probe first:
  `curl -s http://localhost:5001/health` (athena), `ss -ltnp | grep -E ':(5000|5001|8080)'`.
  A stale `athena`/`trino` container from an earlier run invalidates timing
  and log checks — verify its start time before trusting a failure.
- Treat the local stack's data as the user's: S3 buckets and Glue catalogs are
  read-only during validation; create throwaway buckets for writes.

## 6. Close the step

- Run the full gate and put the results in the **commit body**, never in a
  doc: `make format lint type-check test coverage complexity dependencies
  security` + `uv run lint-imports`, plus bandit / vulture / xenon where wired
  (architecture §8.4 table).
- Commit each step with a conventional commit (`feat:`, `fix:`, `test:`,
  `docs:`).
- Update the working docs by **editing** them — one line per item, no appended
  corrections, no dated blocks: check the box in `backlog.md` (and the
  milestone step in `milestones.md`).
- Closes a risk: mark it handled in `architecture.md` §11.
- Code comments state their fact so it stands alone; they may cite an ADR or
  the canonical model path, never a milestone/backlog/PRD ID and never
  `research_repos/` as the sole authority.
- When the emulator ships a capability (verified by a consumer suite a human
  runs): permanent-doc sync only if the architecture moved (ADR-0002…0009
  already lock the design).
- Stop, and report: what shipped, what you measured, what the next item is.