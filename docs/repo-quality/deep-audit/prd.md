# PRD — Repo Deep Audit (EPHEMERAL)

> **EPHEMERAL PRODUCT REQUIREMENT DOCUMENT — working document.**
> It will drift. Do **not** quote PRD content, IDs, or wording in code,
> docstrings, or comments. Code comments may reference only the permanent
> docs (`docs/repo-quality/deep-audit/methodology.md`,
> `docs/repo-quality/deep-audit/adr/*`).

## 1. Goals

A complete, measured audit of every workspace package — down each callstack —
producing (a) an evidence report per package, (b) a finding register of
measured gaps, and (c) small fix items that close real defects without
destabilizing the repo. The existing gate-parity work (`docs/repo-quality/`,
complete) made quality measurable; this workstream makes it verified.

## 2. Non-goals

- Rewriting packages, changing public APIs, or "improving" code with no
  demonstrated harm.
- Re-litigating style that `ruff format`/`lint` already settle.
- Re-running proof the consumer suites already provide (athena-local wire
  parity CS-*, sagemaker_* training runs QH-4).
- One-shot big-bang cleanup — remediation ships item-by-item, gates green.

## 3. Process contract (all FRs rest on this)

- Audits (`AU-*`) are read-only sessions producing a report + gap rows; fixes
  are separate `AF-*` items (ADR-0002).
- A finding earns a severity only with a measurement or failing test
  (ADR-0001); suspects without measurement stay in the report.
- Every fix is TDD, gates green (`make quality` + `lint-imports` + pre-commit
  hooks), one commit per item.
- Working docs are updated by editing rows in place — check the box, no
  dated correction blocks.

## 4. Functional requirements — what each package audit must produce

| ID | FR | Methodology ref | Acceptance |
|---|---|---|---|
| FR-A-01 | Surface inventory: every module, public class/function, and entry point enumerated | §3.1 | Report §"Surface inventory" lists all of them |
| FR-A-02 | Callgraph: every entry point walked to leaf boundaries; dead-looking branches flagged | §3.2 | Report §"Callgraph" covers 100% of public entry points |
| FR-A-03 | Asymptotic table: dominant complexity per public function with measurement | §4 D2, §6 | Report lists big-O + benchmark/count evidence for hot paths |
| FR-A-04 | Type-honesty verdict: every cast/Any/Optional boundary judged honest or flagged | §4 D3, ADR-0004 | Report quotes each suspect signature `file:line` + verdict |
| FR-A-05 | Design-fit verdict: each abstraction earns its place or is flagged as ceremony | §4 D4 | Each flagged abstraction has the "does anything vary?" answer |
| FR-A-06 | Correctness + boundary table: external touches listed, error paths reviewed | §4 D1 + §3.4 | Boundary table complete; each D1 suspect measured or test-demonstrated |
| FR-A-07 | Memory + race probes where the package holds state or concurrency | §4 D6/D7, §6 | tracemalloc/stress evidence, or written single-threaded argument |
| FR-A-08 | Security pass on request parsing, path/subprocess/yaml/pickle/secrets surfaces | §4 D8 | Each applicable surface named; suspects carry exploit-shaped evidence |
| FR-A-09 | Unit-test quality verdict: AAA shape, named fakes, assertion strength (mutation spot-check) | §4 D9, ADR-0005 | Report states mutation-check result + fake inventory |
| FR-A-10 | Integration verdict: pytest-bdd coverage of user-facing surfaces | §4 D10 | Report maps public surfaces → bdd scenarios or names the gap |
| FR-A-11 | Gap rows promoted to `gaps.md` with severity + candidate fix surface | §3.6, §5 | Every confirmed finding is a register row |
| FR-A-12 | Per-item sizing: audits stay one-session-sized; oversized items split first | prompt-execution §2 | No report covers > ~1800 src LOC |

## 5. Non-functional requirements

| ID | NFR | Enforcement |
|---|---|---|
| NFR-A-01 | Fixes are TDD; regression tests for defects | `make test` per fix item |
| NFR-A-02 | Gates stay green; no weakening floors/ignores to hide findings | `make quality`, `lint-imports`, pre-commit |
| NFR-A-03 | No `any`/`Dict` introduced; functions 4–20 lines; files < 500 | pyright strict, repo rules |
| NFR-A-04 | External I/O tested via named fakes; bdd for user-facing behavior | ADR-0005 |
| NFR-A-05 | Numbers in evidence, not adjectives ("12.4 ms @ n=10⁴", not "slow") | methodology §6 |

## 6. Acceptance for the workstream

Done when: every package in the README inventory has an audit report; every
report's findings are triaged in `gaps.md`; every S1/S2 gap has shipped an
`AF-*` fix or a written waiver; `AX-*` cross-cutting sweeps have run; and the
register is either empty or carries only documented residual risk.
