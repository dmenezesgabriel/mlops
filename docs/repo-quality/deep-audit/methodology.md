# Deep-audit methodology (PERMANENT)

How a package audit runs: the dimensions every symbol is checked against, the
measurement each claim must carry, the severity classes, and the report
template. This is the permanent companion to the ephemeral working docs
(`backlog.md`, `gaps.md`, `audits/`).

## 1. Purpose and scope

Verify — with evidence — that each of the 21 workspace packages (plus
`docker/moto/glue_overlay.py` and `projects/athena_emulator` glue) is correct,
typed honestly, appropriately designed, performant, free of leaks/races/
vulnerabilities, and covered by meaningful tests. The gates (QG-1…QG-9) proved
every package *runs* the checks; this audit asks whether the code *deserves*
to pass them.

Out of scope: changing behavior without a demonstrated defect; style
re-litigation the formatter already settles; re-verifying what a consumer
suite already proves (e.g. athena-local wire parity is CS-*'s job — the audit
covers internal quality: retention, asymptotics, typing, races).

## 2. Audit order

Dependency-first (measured in the README inventory): `mlops-shared` →
`data-science-scaffold` → `docker/moto` → `ssg` → its entry-point plugins
(`ssg-syntax-highlighting`, `ssg-latex`, `ssg-notebook-render`, `ssg-i18n` →
`ssg-i18n-machine-translation`) → `diagrams` → `videos` → `videos-linter` →
`sagemaker-local` → the `sagemaker_*` projects → `ml_specialization` →
`nyc_taxi_demand_forecasting` → `projects/athena_emulator` → `athena-local`
(per plane). A package's contracts are verified before the code that relies on
them, so later audits can check consumers against known-good interfaces.

## 3. Per-package procedure

1. **Surface inventory** — list every module, public class, and public
   function; note entry points (CLI mains, entry-point plugins, pipeline
   `run()`s, handlers). Cheap: `grep -n "def \|class "` + `radon raw`.
2. **Callgraph walk** — from each entry point, walk the callstack to the
   leaves. Record the reachable subgraph in the audit report as an indented
   trace `entry → callee → boundary`; flag unreachable-looking code (vulture
   corroborates).
3. **Dimension walk** — for each symbol on the callgraph, run D1…D10 (§4).
   Suspects get a measurement (§6) or a failing test before they become gap
   rows.
4. **Boundary table** — list every external touch (filesystem, network,
   subprocess, SDK, entry-point loading, env, time, RNG) and confirm each is
   injectable/fakeable and that the current tests fake it with *named* fakes.
5. **File the report** — `audits/AU-NN-<slug>.md` per the §7 template:
   inventory, callgraph, measurements, boundary table, and the gap rows
   produced (with `file:line` anchors).
6. **Promote** — copy confirmed findings into `gaps.md` (one row each);
   severity sets scheduling per §5.

## 4. Dimension rubric

| ID | Dimension | What to check | How to prove it |
|---|---|---|---|
| D1 | Correctness | Edge cases, error paths, off-by-one, invariants, spec fidelity; `except` scope; silent fallbacks | Failing-test demonstration or spec citation; happy-path coverage ≠ correctness |
| D2 | Asymptotics | Inner loops over unbounded data; repeated normalization; quadratic scans; `list(x)` copies in loops; N+1 calls | Scaling microbenchmark (n = 10²/10³/10⁴, log-log slope) or operation count with `file:line` |
| D3 | Type honesty | `cast()` without an invariant comment; `Any`/`object` outside a documented boundary; `Optional` hiding error paths; mutable defaults; `dict[str, Any]` for structured payloads; return-type lies | Reading + pyright strict; a cast/Any is honest only if its comment names the runtime invariant |
| D4 | Design fit | Patterns that earn their place (ports/adapters at real seams, factory at real variation); ceremonial layers that don't (pass-through wrappers, speculative registries, DI into stable deps) | Reading; the test: delete the abstraction — does anything actually vary? |
| D5 | Clarity / discoverability | Specific names (no `data`/`handler`/`Manager`), predictable module paths, public API surface documented (`__all__`/docstrings), no god files | Reading + the repo rules (files < 500, functions 4–20) |
| D6 | Memory | Unbounded growth (stores, caches, registries, history lists); retained handles; per-request accumulation; large-object copies | `tracemalloc` diff across N repeated calls; registry size counters; `gc`/`weakref` checks |
| D7 | Concurrency | Shared mutable module/ClassVar state; TOCTOU on filesystem/paths; unguarded counters; thread/async hazards; forked logging config | Stress test (threads × repeated calls) or explicit "single-threaded by construction" argument |
| D8 | Security | Injection (SQL/shell/template); path traversal on joins; `yaml.load` vs `safe_load`; pickle/joblib trust; subprocess arg shape; secret handling/logging; request parsing | Reading + targeted exploit-shaped test; bandit/semgrep already gate — audit covers what linters can't see |
| D9 | Unit tests | AAA shape (Arrange/Act/Assert), named fakes at boundaries, assertion strength (a mutant flip must fail something), F.I.R.S.T. | Reading + coverage report + ≥1 manual mutation spot-check per core module |
| D10 | Integration tests | pytest-bdd scenarios covering user-facing behavior (CLI, service endpoints, pipeline runs); real/production-like deps at the seams the unit tests fake | `pytest --collect-only` of `features/` + reading; gap = public surface with no bdd scenario |

## 5. Severity rubric and scheduling

| Class | Meaning | Scheduling |
|---|---|---|
| S1 | Correctness defect, exploitable vuln, or race/data-loss risk — demonstrated | Promote to an `AF-*` item; fixes are scheduled before the next audit item |
| S2 | Measured perf/memory risk | `AF-*` item in the current milestone's remediation step |
| S3 | Type/design/clarity debt | `AF-*` item, batched in the remediation step |
| S4 | Test gap | `AF-*` item, batched; a missing-bdd-surface gap also tags AX-2 |
| Waived | Real but accepted (bounded input, dead CLI path, etc.) | Written reason on the gap row; a waived S1 needs a maintainer-visible justification |

Reading alone can only produce a *suspect*. A row gets a severity when it
carries a measurement or a failing test (ADR-0001).

## 6. Measurement standards (ADR-0003)

- **Asymptotics**: `timeit`/`perf_counter` on the real function at three
  input sizes; report times + inferred slope. For non-runnable internals,
  count dominant-loop iterations with `file:line` evidence instead.
- **Memory**: `tracemalloc.start()` → warm call → `tracemalloc` diff after N
  iterations; or object-count deltas for store-style classes.
- **Races**: `threading` stress harness over the shared path (≥1000 ops),
  or a written single-threaded-by-construction claim citing the entry points.
- **Perf claims in fixes**: before/after numbers in the audit report and
  commit body; no "should be faster".
- **Type honesty**: quote the signature + the `file:line`; state the true
  runtime contract and why the annotation diverges.

## 7. Audit report template (`audits/AU-NN-<slug>.md`)

```markdown
# AU-NN — <package> audit (YYYY-MM-DD)

## Surface inventory
<modules × public symbols table; entry points starred>

## Callgraph
<indented trace per entry point; unreachable branches flagged>

## Boundary table
| Boundary | Where | Faked as | Test |
|---|---|---|---|

## Dimension findings
| Dim | Suspect / measured | Evidence | Disposition |
|---|---|---|---|

## Measurements
<benchmarks, tracemalloc diffs, stress runs, mutation checks>

## Gaps promoted
| Gap ID | Severity | One-line |
|---|---|---|
```

Keep it dense — one fact per row, `file:line` everywhere, no prose padding.
The report is the evidence behind every gap row it produces.

## 8. Risks of the audit itself

- **False-positive churn** — reading flags ghosts. Mitigation: severity
  requires measurement (§5); suspects stay in the report, not the register.
- **Audit fatigue / scope creep** — mitigated by one item per session and
  fixed-size reports; an oversized item is split in `backlog.md` first.
- **Fixing non-defects** — a gap row must name the demonstrated harm; "could
  be cleaner" is not a fix target.
- **Gate regression theater** — fixes must not weaken floors, add `type:
  ignore`, or add noqa/pragma to hide findings; the honest fix is required.
