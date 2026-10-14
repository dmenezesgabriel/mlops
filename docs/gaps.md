# Gap register (EPHEMERAL)

> **EPHEMERAL WORK REGISTER — iterates freely; never cited from code.**
> One row per *measured* finding: a benchmark number, a tracemalloc diff,
> a stress-run failure, an exploit-shaped repro, or a spec citation that
> pins the divergent behavior
> (`methodology/deep-audit/adr/0001-measured-evidence-required-for-severity.md`).
> Suspects without measurement stay in the flagging report's "Dimension
> findings" table — visible, not registered.

| ID | Package | Location | Dim | Severity | Measured finding | Candidate fix | Disposition |
|---|---|---|---|---|---|---|---|
| G-325 | ssg-i18n | `site/site.yaml` `translation_mode` + root `pyproject.toml` dev deps | D5 | S3 | `make build-site` exits 1: `manual_with_machine_fallback` mode hits `CatalogFirstTextTranslator` misses (~240 pt-BR strings, measured 2026-10-14) → machine fallback → `RuntimeError: Missing dependency 'transformers'`; root dev deps install `ssg-i18n-machine-translation[evaluation]` only, so the venv lacks the `transformers` extra the configured mode requires | Add the `transformers` extra to the workspace dev deps, or declare `build-site` requires it; alternatively keep `site/i18n/pt-BR.yaml` complete so the fallback never fires | shipped 2026-10-14 — AF-175: dev deps carry `ssg-i18n-machine-translation[evaluation,transformers]`; `make build-site` exits 0 with machine pt-BR output |

- IDs are sequential `G-NN` repo-wide — next free number is **G-326**
  (G-01…G-324 are dispositioned in `docs/archive/repo-quality/deep-audit/
  gaps.md`; athena-emulator's GP-* register is in
  `docs/archive/athena-emulator/gaps.md`).
- Severity S1–S4 + waived per
  `docs/methodology/deep-audit/methodology.md` §5; a waived row requires a
  written reason.
- A row leaves the register when its fix ships (the measured evidence
  flips) or is waived.
