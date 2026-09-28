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

## MA-1 — Spike (calibration)

- [ ] **AU-01** `libs/mlops-shared` — smallest foundation, depended on by all
  projects. Proves the rubric end-to-end and produces the effort-vs-size
  datapoint that re-splits any oversized remaining item.
- [ ] Recalibrate: if the spike's effort-to-LOC ratio suggests mis-sizing,
  split `L` items further in `backlog.md` before proceeding.
- [ ] Ship promoted `AF-*` (if any) + mark gap rows.

## MA-2 — Foundations

- [ ] **AU-02** `data-science-scaffold` (generates the `projects/*` skeleton —
  template defects here replicate into AU-17/AU-18, so it audits first).
- [ ] **AU-03** `docker/moto/glue_overlay.py` (wire-parsing — D8 heavy).
- [ ] Remediate promoted S1+ gaps.

## MA-3 — SSG core

- [ ] **AU-04** `ssg` domain + application.
- [ ] **AU-05** `ssg` infrastructure + CLI — includes the entry-point loading
  contract every plugin in MA-4 implements; its verdicts are reused.
- [ ] Remediate promoted S1+ gaps.

## MA-4 — SSG plugins

- [ ] **AU-06** syntax-highlighting → **AU-07** latex → **AU-08**
  notebook-render → **AU-09** i18n → **AU-10** i18n-machine-translation
  (dependency order: i18n-mt implements i18n's translator port).
- [ ] Remediate promoted S1+ gaps.

## MA-5 — Media family

- [ ] **AU-11** diagrams → **AU-12** videos domain+app → **AU-13** videos
  infra+cli → **AU-14** videos-linter (depends on videos).
- [ ] Remediate promoted S1+ gaps.

## MA-6 — ML workspace

- [ ] **AU-15** sagemaker-local → **AU-16** `sagemaker_*` batch → **AU-17**
  ml_specialization → **AU-18** nyc_taxi → **AU-19** athena_emulator parity.
- [ ] Remediate promoted S1+ gaps.

## MA-7 — athena-local (per plane)

- [ ] **AU-20** protocol → **AU-21** state → **AU-22** SQL rewrite →
  **AU-23** iceberg → **AU-24** execution → **AU-25** boundary/artifacts →
  **AU-26** test-suite quality.
- [ ] Remediate promoted S1+ gaps.

## MA-8 — Cross-cutting + close

- [ ] **AX-1** repo-wide pattern sweep (patterns flagged ≥2×).
- [ ] **AX-2** user-facing surface → bdd scenario matrix; S4 rows promoted.
- [ ] Ship remaining `AF-*`; **AX-3** close-out — register dispositioned,
  seeds resolved, docs marked complete.
