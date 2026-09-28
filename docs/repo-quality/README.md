# Repo-wide quality-gate parity — documentation index

Bring every uv-workspace package up to the `libs/athena-local` static-check
standard: ruff format+lint, pyright, pytest, pytest-cov, radon, xenon,
vulture, bandit, semgrep, deptry, import-linter — wired as per-package
`make` targets reachable from the root `make quality` loop, with findings
tracked and fixed item by item.

## Documentation map

| Path | Kind | Status |
|---|---|---|
| [backlog.md](backlog.md) | **Ephemeral** — evidence-anchored work items, one measured gate gap or finding fix per row | Must NOT be cited from code |
| [milestones.md](milestones.md) | **Ephemeral** — ordered phases: audit → wiring → findings → floors/strictness | Must NOT be cited from code |

Rule enforced repo-wide: **backlog and milestones are ephemeral working
documents; never quote their IDs or content in code, docstrings, or
comments.**

## Conventions used in these documents

- **Evidence citations** are repo-relative paths with `:line` anchors, plus
  measured numbers from tool runs recorded in the row that consumed them.
- **Canonical gate pattern**: `libs/athena-local/Makefile` +
  `libs/athena-local/pyproject.toml` (the fullest gate set) and
  `docs/athena-emulator/architecture.md` §8.4 (the gate table).
- **Scan scope**: complexity gates (radon, xenon) cover the whole package
  directory including tests; bandit and vulture cover `src` (athena's
  recipe scope). Vendored trees (e.g. `*/node_modules/*`) are excluded via
  each tool's real exclusion flag.
- **Process rule**: every source change is TDD where behavior changes;
  pure refactors keep existing tests green. Every commit keeps
  `make quality` green — a recipe flip that exposes findings ships in the
  same commit as (or after) the fixes it requires.

## Measured audit index (2026-09-27)

| Topic | Anchor |
|---|---|
| Broken radon recipe — `-x` is radon's `--max` (grade bound), not `--exclude` (`-e`); `-x "*/node_modules/*"` suppresses all output in 13 Makefiles | `radon cc --help`; `libs/*/Makefile` `complexity` targets |
| Xenon whole-package failures (athena bar, `.` scope) | `libs/athena-local` 16 errs (tests), `libs/videos-linter` 5, `libs/videos` 4, `libs/ssg-latex` 3 (vendored katex), `projects/nyc_taxi_demand_forecasting` 2, `libs/ssg`/`ssg-i18n-mt`/`ssg-notebook-render`/`sagemaker-local` 1 each |
| Bandit findings | `libs/ssg` B704 ×5 (`markupsafe.Markup`) |
| Vulture findings (`--min-confidence 80`, `src`) | `libs/mlops-shared` 3, `libs/videos` 3, `libs/ssg-i18n-machine-translation` 2, `libs/ssg-latex` 2 |
| Packages unreachable via root `make quality` | root `Makefile` `PACKAGES` omits `projects/ml_specialization` + `projects/sagemaker_*` ×4 (all uv-workspace members) |
| Packages missing gate targets | `libs/sagemaker-local` (5), `projects/sagemaker_*` (5 each) |
| Pre-commit scope | `bandit`/`vulture`/`xenon` hooks limited to `files: ^libs/athena-local/` |

## Implementer starting point

Read `milestones.md` for the current phase, then the item's row in
`backlog.md` — its evidence cell names the exact files and measured
numbers. Execute one item, keep `make quality` green, check the box.
