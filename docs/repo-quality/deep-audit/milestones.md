# Deep-audit milestones (EPHEMERAL)

> **EPHEMERAL PHASES — iterate freely; never cited from code.** Ordered;
> each milestone's remediation step ships that milestone's promoted `AF-*`
> items before the next audit phase begins. Items: `backlog.md`. Rubric:
> `methodology.md`.

## MA-0 — Bootstrap ✅ (this session)

- [x] Doc set: README, methodology, prd, prompt-execution, backlog,
  milestones, gaps, ADR-0001…0005 under `docs/repo-quality/deep-audit/`.
- [x] Package inventory measured (src/test LOC per package, dependency edges
  via pyproject `dependencies` + entry points).
- [x] Parent `docs/repo-quality/README.md` doc map points here.

## MA-1 — Spike (calibration) ✅

- [x] **AU-01** `libs/mlops-shared` — smallest foundation, depended on by all
  projects. Proves the rubric end-to-end and produces the effort-vs-size
  datapoint that re-splits any oversized remaining item.
- [x] Recalibrate: if the spike's effort-to-LOC ratio suggests mis-sizing,
  split `L` items further in `backlog.md` before proceeding. (Verdict:
  sizing holds — suspect count, not LOC, drives effort; all `L` items are
  pre-split by plane ≤~1600 LOC.)
- [x] Ship promoted `AF-*` + mark gap rows. (AF-01/S1 + AF-02 + AF-03 +
  AF-04 + AF-05 + AF-06 shipped; G-07 waived, surface deleted by AF-05.)

## MA-2 — Foundations

- [x] **AU-02** `data-science-scaffold` (generates the `projects/*` skeleton —
  template defects here replicate into AU-17/AU-18, so it audits first).
  9 gaps (S3×8, S4×1) — template gate drift + anchor-fragile registration.
- [x] **AU-03** `docker/moto/glue_overlay.py` (wire-parsing — D8 heavy).
  8 gaps (S1×1, S3×6, S4×1) — stale column statistics resurrect on
  table/db recreate; `ColumnNames` ignored; malformed stat entry → 500;
  dead UDF store; apply-guard + type-fold parity nits; 78% cov.
- [x] Remediate promoted S1+ gaps. (AF-07…AF-19 all shipped — every
  AU-02/AU-03 gap dispositioned; AF-14 carried the S1, AF-19 closed the
  G-27 test-depth row.)

## MA-3 — SSG core

- [x] **AU-04** `ssg` domain + application. 12 gaps (S1×1, S2×1, S3×9, S4×1) —
  preview rebuild no-op via per-call fresh dependency tracker (S1);
  `--collection` nav leaks unbuilt collections; empty collection crashes;
  `trigger_reload` off-protocol; O(n²) nav+pager; dead `page_by_slug`/
  `aria_current`; wiring-seam test gap.
- [x] **AU-05** `ssg` infrastructure + CLI. 15 gaps (S3×14, S4×1) — CLI
  tracebacks on all error paths; Jinja-over-markdown evals/crashes on literal
  `{{`; unvalidated entry-point contract; dead `PollingSiteReloader`;
  coverage-invisible preview server.
- [x] Remediate promoted S1+ gaps. (AF-20…AF-35 all shipped — every AU-04/AU-05
  gap dispositioned; G-39's `build`/`preview`/`--collection` surfaces tagged
  for AX-2; G-54 closed with the coverage-visible preview server.)

## MA-4 — SSG plugins

- [x] **AU-06** syntax-highlighting — 7 gaps (S3×6, S4×1): HTMLParser
  re-serialization emits phantom end tags (`<br/>`→`<br></br>` doubles line
  breaks, reachable via markdown hard breaks and prose-`language-` pages),
  drops comments/decls/PIs, double-decodes entities into the lexer, drops
  unclosed-code capture; per-page formatter ~60% of 1-block render cost;
  5/5 mutants survived at 100% line coverage.
- [x] **AU-07** latex → **AU-08**
  notebook-render → **AU-09** i18n → **AU-10** i18n-machine-translation
  (dependency order: i18n-mt implements i18n's translator port).
  AU-07: 10 gaps (S1×1, S2×1, S3×7, S4×1); AU-08: 9 (S3×8, S4×1);
  AU-09: 22 (S1×2, S2×2, S3×17, S4×1); AU-10: 14 (S1×1, S2×1, S3×11, S4×1) —
  evaluator false-green on missing/divergent input (S1); translator
  locale-blind for non-nllb models; model load × locale × rebuild (S2).
- [x] Remediate promoted S1+ gaps. (AF-36…AF-64 all shipped — every
  AU-06…AU-10 gap dispositioned; `ssg-i18n-evaluate` + EP surface tagged
  for AX-2.)

## MA-5 — Media family

- [x] **AU-11** diagrams → **AU-12** videos domain+app → **AU-13** videos
  infra+cli → **AU-14** videos-linter (depends on videos).
  (All four audits done; 54 open gaps — S1×3, S3×46, S4×5 — awaiting the
  remediation step below. AU-14 carried the S1s: the advanced linter
  silently green-lights missing/corrupt artifacts and has two measured
  false-PASS paths — phantom `[30,30,30]` background, same-channel overlap
  merge.)
- [x] Remediate promoted S1+ gaps. (AF-65…AF-79 all shipped — every
  AU-11…AU-14 gap dispositioned; register has zero open rows.)

## MA-6 — ML workspace

- [x] **AU-15** sagemaker-local → **AU-16** `sagemaker_*` batch → **AU-17**
  ml_specialization → **AU-18** nyc_taxi → **AU-19** athena_emulator parity.
  (AU-15 done; its 14 gaps remediated via AF-80…AF-86, e2e-sweep gaps via
  AF-87…AF-90 — AF-91 still open. AU-16 done: 4 open gaps — S3×3, S4×1 —
  `SM_HPS` raw-parse boundary on all 4 `train.py` clones, scikit's doubled
  `fetch_california_housing`, `build_model` annotation asymmetry, test
  assertion depth. AU-17 done: S1 shipped via AF-92/93 (ndarray pyfunc
  predict 500s); 15 open — S3×13, S4×2 — pipeline `run()`s log
  "completed" over an unwired stub surface that fabricates artifacts;
  coverage gate green at polluted 84% while scoped own-tree is 73% < 75
  floor. AU-18 done: S1×3 shipped via AF-94/95/96 (`shift(-1)` labels,
  ungated promotion, cwd-relative `tracking_uri`); 21 open — S3×20,
  S4×1 — `include:` stubs, monitor `@champion` fallback lie, hardcoded
  `+0.00%` drift rows, feast `apply(repoB)` gets repoA's objects.
  AU-19 done: 12 open — S3×10, S4×2 — recorded FAIL verdicts never turn
  the run red, README's host pytest path errors on missing `nbclient`,
  import-time health probe escapes `except OSError` on non-HTTP endpoints,
  `_evidence.py` has zero unit tests, `persist` allows `../` escapes +
  loses sections under concurrent writers, the glue is outside every gate
  but pre-commit ruff.)
- [x] Remediate promoted S1+ gaps. (AF-80…AF-117 all shipped — every
  AU-15…AU-19 gap dispositioned; register has zero open rows.)

## MA-7 — athena-local (per plane)

- [ ] **AU-20** protocol ✅ (3 gaps — S3×2, S4×1; G-248 NextToken
  accepts negative/padded tokens, G-249 raw-wire member constraints
  unenforced, G-250 guard/branch test gaps) → **AU-27** protocol handlers ✅
  (5 gaps — S3×4, S4×1; G-251 list-op caps unenforced, G-252 per-op member
  constraints unenforced, G-253 ClientRequestToken idempotency ignored,
  G-254 tag-count quota unenforced breaks the no-pagination argument,
  G-255 malformed-ARN raises untested) →
  **AU-21** state ✅ (5 gaps — S3×4, S4×1; G-256 ListPreparedStatements
  MaxResults unenforced, G-257 PS member constraints unenforced, G-258
  unknown-workgroup create accepted where moto 400s, G-259 double kwarg
  wall in ExecutionStore.create + SubmissionPlanner.create_record, G-260
  empty-prefix branch uncovered everywhere + absent-Parameters keep-branch
  unasserted; D6 retention verified — the "unbounded stores" seed is
  resolved by the shipped TTL+cap; D7 holds — 4000-op stress) →
  **AU-22** SQL rewrite ✅ (3 gaps — S3×2, S4×1; G-261 comment-blind lexers
  on the un-stripped submit path break all three rewrites into pass-through,
  G-262 `_parse_type` RecursionError at 331 nested types → 500 where Athena
  400s, G-263 51 guard-arm stmts uncovered + M-7/M-8 mutants survive; D8
  clean, D2 linear, D7 16k-call stress; SORTED BY pass-through correct per
  the AWS synopsis) → **AU-23** iceberg ✅ (4 gaps — S2×1, S3×2, S4×1;
  G-264 comment-blind clause parsing mis-rewrites PARTITIONED BY comments
  into garbage partition columns + bails elsewhere, G-265
  EXTRACT/TRIM/UNNEST FROM-arguments falsely catalog-qualified on an
  iceberg name collision, G-266 quadratic comment scaling — 32.6 s @ 10k
  comments, 187k chars < cap, G-267 guard-arm/mutation test depth; D6
  clean — cache bounded 10k/3.7 MB, D7 holds — construction + 8000-op
  stress, D8 clean — escaping probed) → **AU-24** execution ✅ (9 gaps —
  S1×3, S3×5, S4×1; G-268 concurrent same-token StartQueryExecution
  double-executes — 2 ids/2 Trino submissions, G-269 cancel inside
  `await writer.write` dies as an unretrieved CANCELLED→SUCCEEDED ValueError,
  G-270 QUEUED-cancel never DELETEs the preflight-submitted statement —
  37/40 stress cancels unstopped; G-271 ClientRequestToken 1..36 vs model
  32..128, G-272 ExecutionParameters/Database member bounds unenforced,
  G-273 BatchGet 51-ids cap + MaxResults=0, G-274 parenthesized queries →
  UTILITY/None + `.txt` → wrangler empty DataFrame, G-275 backtick spans
  unlexed by the placeholder/USING scanners, G-276 8/571 stmts uncovered +
  M-2 survives; D2 linear 0.89-0.99, D6 documented live-count bound,
  D8 clean, D10 live CLI/consumer suites; AU-24's S1s preempt AU-25 —
  AF-118 shipped, AF-119/AF-120 pending) →
  **AU-25** boundary/artifacts → **AU-26** test-suite quality.
- [ ] Remediate promoted S1+ gaps.

## MA-8 — Cross-cutting + close

- [ ] **AX-1** repo-wide pattern sweep (patterns flagged ≥2×).
- [ ] **AX-2** user-facing surface → bdd scenario matrix; S4 rows promoted.
- [ ] Ship remaining `AF-*`; **AX-3** close-out — register dispositioned,
  seeds resolved, docs marked complete.
