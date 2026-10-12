# Repo Deep Audit — documentation index

Walk every workspace library and application down its callstack — every public
class, method, and function — and measure, not assume: asymptotic behavior,
type-signature honesty, design-pattern fit, correctness, memory retention,
races, vulnerabilities, and test depth (pytest AAA unit + pytest-bdd
integration). Findings land in the gap register and ship as small, reviewable
fix items — never as one broad refactor.

Scope: the 21 Python packages the root `Makefile` `PACKAGES` loop exercises
(`make quality`, `make audit` QG-9), plus `docker/moto`'s `glue_overlay.py`
and the `projects/athena_emulator` parity-notebook glue. `docs/repo-quality/`
(gate-parity work, complete) made every package *measurable*; this workstream
makes every package *verified*.

**Status: complete 2026-10-12** — 27 package audits + 2 cross-cutting sweeps;
324 measured gaps dispositioned (323 shipped via `AF-*` items, 1 waived with
written reason); all known risk seeds below resolved.

## Documentation map

| Path | Kind | Status |
|---|---|---|
| [methodology.md](methodology.md) | **Permanent** — audit rubric: dimensions, measurement standards, severity classes, report template | Keep in sync with practice |
| [adr/](adr/) | **Permanent** — methodology decisions (Nygard-style, numbered, append-only) | Supersede only with a new ADR |
| [prd.md](prd.md) | **Ephemeral** — audit requirements (what each package audit must produce + acceptance) | Must NOT be cited from code |
| [prompt-execution.md](prompt-execution.md) | **Operational** — session execution protocol, mapped to this repo's files | Keep in sync with doc map |
| [backlog.md](backlog.md) | **Ephemeral** — audit items `AU-*`, fix items `AF-*`, cross-cutting `AX-*` | Must NOT be cited from code |
| [milestones.md](milestones.md) | **Ephemeral** — ordered phases MA-0…MA-8 | Must NOT be cited from code |
| [gaps.md](gaps.md) | **Ephemeral** — measured finding register, one small-step fix sketch per row | Must NOT be cited from code |
| [audits/](audits/) | **Ephemeral** — one evidence report per completed `AU-*` item (`AU-NN-<slug>.md`) | Must NOT be cited from code |

Rule enforced repo-wide: **PRD, backlog, milestones, gaps, and audit reports
are ephemeral working documents; never quote their IDs or content in code,
docstrings, or comments.** Code comments may reference only permanent
artifacts (`methodology.md`, `adr/000N-*.md`) and shall cite *evidence*
(file:line), never the working document that produced the finding.

## Conventions used in these documents

- **Evidence citations** are repo-relative `file:line` anchors plus measured
  numbers (benchmarks, counts, coverage %). Reading alone may flag a
  *suspect*; a severity requires a measurement or a failing test (ADR-0001).
- **Audit items are read-only** — an `AU-*` session produces a report and gap
  rows only; every confirmed finding becomes an `AF-*` fix item (ADR-0002).
- **Severity classes**: S1 correctness/security/race defect → fix next;
  S2 measured perf/memory risk; S3 type/design/clarity debt; S4 test gap.
  Waived rows require a written reason (methodology §5).
- **Standards**: ADRs per the Nygard "Architecture Decision Records" format
  (Status · Context · Decision · Consequences); audits follow
  `methodology.md`; every step derives from evidence, never invention.
- **Process rule**: fixes are TDD (red → green → refactor). Quality gates run
  at every commit: pytest, pytest-cov, pytest-bdd, pyright, ruff, bandit,
  vulture, xenon, radon, semgrep, import-linter, deptry — wired as pre-commit
  hooks and per-package `make quality` (QG-1…QG-9).

## Package inventory (measured 2026-09-26: `find … | wc -l`)

Audit order is dependency-first: a package's contracts are verified before the
plugins/consumers built on them. Lines are `wc -l` of `src/**/*.py` / `tests`.

| Pkg | Path | Src LOC | Test LOC | Depends on (workspace) | Audit item |
|---|---|---|---|---|---|
| mlops-shared | `libs/mlops-shared` | 276 | 204 | — | AU-01 (spike) |
| data-science-scaffold | `libs/data-science-scaffold` | 152 | 161 | — | AU-02 |
| glue_overlay | `docker/moto` | 357 | (in pkg) | moto server | AU-03 |
| ssg (domain+app) | `libs/ssg` | ~670 | 2296 | — | AU-04 |
| ssg (infra+cli) | `libs/ssg` | ~1470 | 〃 | — | AU-05 |
| ssg-syntax-highlighting | `libs/ssg-syntax-highlighting` | 229 | 204 | ssg (entry point `ssg.html_post_processors`) | AU-06 |
| ssg-latex | `libs/ssg-latex` | 282 | 309 | ssg (`ssg.html_post_processors`) | AU-07 |
| ssg-notebook-render | `libs/ssg-notebook-render` | 485 | 402 | ssg (`ssg.renderers`) | AU-08 |
| ssg-i18n | `libs/ssg-i18n` | 1135 | 1057 | ssg (`ssg.site_variant_providers`) | AU-09 |
| ssg-i18n-machine-translation | `libs/ssg-i18n-machine-translation` | 603 | 468 | ssg-i18n (`ssg_i18n.text_translators`) | AU-10 |
| diagrams | `libs/diagrams` | 408 | 399 | — (CLI `diagrams-cli`) | AU-11 |
| videos (domain+app) | `libs/videos` | ~1400 | 4165 | — | AU-12 |
| videos (infra+cli) | `libs/videos` | ~1600 | 〃 | manim | AU-13 |
| videos-linter | `libs/videos-linter` | 457 | 335 | videos | AU-14 |
| sagemaker-local | `libs/sagemaker-local` | 619 | 901 | sagemaker sdk, moto | AU-15 |
| sagemaker_{scikit_learn,catboost,lightgbm,xgboost} | `projects/sagemaker_*` | ~300 (4×~75) | ~966 | shared `train.py` shape | AU-16 (batch) |
| ml_specialization | `projects/ml_specialization` | 731 | — | mlops-shared | AU-17 |
| nyc_taxi_demand_forecasting | `projects/nyc_taxi_demand_forecasting` | 1615 | 2211 | mlops-shared, feast, mlflow | AU-18 |
| athena_emulator parity glue | `projects/athena_emulator` | 87 | — | athena-local notebooks | AU-19 |
| athena-local | `libs/athena-local` | 9603 | 24158 | trino, moto | AU-20…AU-26 (per plane) |

Exclusions: `projects/notebooks` (no Python), `projects/ml_monitoring_draft`
(scratch draft with its own `.venv`, not a workspace package).

## Known risk seeds (audit starting points — all resolved 2026-10-12)

Unverified suspicions worth probing — each was measured by its audit; the
resolution follows each seed:

- `libs/athena-local/src/athena_local/state.py` — in-memory stores; unbounded
  growth under long sessions? Pagination off-by-ones (opaque tokens).
  → **Resolved AU-21**: TTL+cap bounds the stores (5000 creates @ cap 500 →
  pinned, tracemalloc 961 KB steady-state); opaque-token off-by-ones shipped
  as canonical NextToken decode + list-op bounds (G-248/G-256/G-280/G-291).
- `libs/sagemaker-local/src/sagemaker_local/patches.py` (317 LOC) — monkey-
  patches the sagemaker SDK; upstream signature drift is the known hazard.
  → **Resolved AU-15**: all patched seams signature-verified against
  sagemaker 2.257.1; drift's real failure mode was decontextualized crashes,
  shipped via G-178-class fixes (AF-80…AF-86).
- `docker/moto/glue_overlay.py` — parses wire requests; request-shape and
  error-path review. → **Resolved AU-03**: 8 gaps shipped (AF-14…AF-19),
  incl. the S1 stale column statistics resurrecting on table/db recreate.
- `libs/videos/…/manim/renderer.py` — subprocess + temp files; resource
  cleanup and argument safety. → **Resolved AU-13**: premise stale — no
  subprocess exists, manim renders in-process; the measured hazards
  (unsorted partial-movie glob, substring temp-dir test, class-level
  non-reentrant lock) shipped via AF-68…AF-79.
- `libs/ssg/…/markdown_content_renderer.py` — per-page O(n) passes; plugin
  entry-point loading. → **Resolved AU-05**: the per-page Jinja-eval pass was
  deleted and the marker/asset collisions shipped (G-42/43/49 → AF-30);
  entry-point loads now contract-validated (G-41 → AF-29).
- `libs/ssg-i18n/…/document_translator.py` (439 LOC) — translation batching;
  repeated normalization passes (a prior perf fix shipped in QF-2 territory).
  → **Resolved AU-09**: measured S2s shipped — glossary `re.compile` per term
  per sentence (0.19→55 ms) and no incremental/scoped translation; the
  marker-heal corruption + Quote/SetextHeading blind spots shipped too.
- `libs/mlops-shared` `config.py`/`logging.py` — global logging state;
  ClassVar-style registries shared across projects. → **Resolved AU-01**:
  clean — no retained registries (tracemalloc flat over 2000 calls),
  single-threaded-by-construction + 8×1000-op stress clean; the real
  findings (log-field spoofing, silent drops, YAML coercion, path escape)
  shipped via AF-01…AF-06.
- `projects/ml_specialization` — zero test LOC recorded; audit starts with a
  coverage/truth measurement. → **Resolved AU-17**: premise stale (280 test
  LOC existed); the coverage truth was the gap — bare `--cov` reported 84%
  polluted while scoped own-tree measured 73% < the 75 floor (G-208,
  remediated; 99.87% own-tree post-MA-6).

## Implementer starting point

The workstream is closed — this doc set is evidence and history. Read
`methodology.md` for the rubric, `audits/` for the per-package evidence, and
`gaps.md` for the measured findings and their dispositions. Keep PRD /
backlog / milestones / gaps / audits out of the code.
