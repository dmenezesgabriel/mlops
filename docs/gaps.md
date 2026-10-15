# Gap register (EPHEMERAL)

> **EPHEMERAL WORK REGISTER — iterates freely; never cited from code.**
> One row per *measured* finding: a benchmark number, a tracemalloc diff,
> a stress-run failure, an exploit-shaped repro, or a spec citation that
> pins the divergent behavior
> (`methodology/deep-audit/adr/0001-measured-evidence-required-for-severity.md`).
> Suspects without measurement stay in the flagging report's "Dimension
> findings" table — visible, not registered.

| ID | Pkg | File:line | Dim | Severity | Measured evidence | Candidate fix surface | Status |
|---|---|---|---|---|---|---|---|
| G-326 | ssg | `static/css/site.css:247-255` + `templates/partials/head.html:2` | D1 | S3 | `.search-input` `font-size: 0.8rem` = 12.8px at the 16px UA root (no `html` font-size override — `site.css:40,45-56`); below iOS Safari's 16px focus auto-zoom threshold, and the viewport tag permits scaling → focusing search zooms the page | raise `.search-input` to ≥1rem (≥16px) under `max-width: 40rem` — or globally | open |
| G-327 | ssg | `static/css/site.css:215-226,227-238,247-255` | D1 | S3 | header tap targets below Apple HIG 44pt / Android 48dp: `.menu-toggle` ≈ 40px (0.65rem pad + ~0.8rem text + 6px border), `.theme-select` ≈ 38px (0.55rem pad), `.search-input` ≈ 38px | `min-height: 44px` (or larger padding) on header controls under `max-width: 58rem` | open |
| G-328 | ssg | `tests/playwright/test_built_site_smoke.py:222,554` | D10 | S4 | playwright mobile coverage pins only the 390px viewport (menu + mobile-TOC); no 320px/768px pass, no `scrollWidth ≤ innerWidth` overflow assertion on any page type | viewport sweep 320/390/768 × index/article/404 + overflow assertion (lands with SX-15) | open |
| G-329 | ssg-i18n-machine-translation | `application/use_cases/machine_translation_evaluator.py:71` | D1 | S1 | `extract_text_nodes` iterates `getattr(node, "children", [])` — mistletoe's `ThematicBreak` and `CodeFence`→`RawText` carry `children = None`, so the default never applies and iteration raises `TypeError: 'NoneType' object is not iterable`; measured 2026-10-15: crashes `make evaluate-translation` on `projects/nyc_taxi_demand_forecasting/docs/*.md` (ThematicBreak ×11 + CodeFence→RawText ×3 across 5 source docs, mirrored in the generated pt-BR set — CI run 38664028338 Build Site job); translator's own guard is `getattr(node, "children", None)` + `if not children` (`ssg-i18n/.../document_translator.py:337-338`) | `for child in getattr(node, "children", None) or []:` — mirrors the translator guard and this file's own `render_node` (`:83`) | shipped |
| G-330 | ssg-i18n-machine-translation | `application/use_cases/machine_translation_evaluator.py:97-101` | D1 | S1 | `is_fallback` flags nodes made only of protected spans as English fallback — measured 2026-10-15 on real docs (`make evaluate-translation`, model `opus-mt-tc-big-en-pt`): 19/154 flagged (12.34% > 8% gate) of which 8 are verbatim-by-design (pure `{{…}}` ×1, pure `$$…$$` math ×7); the translator protects exactly these spans (`document_translator.py:97-101` `_PROTECTED_PATTERN`, `:280-291` math placeholders), so identical output is the contract — the true rate is 11/154 ≈ 7.1% | count `is_fallback` only when letters remain after stripping the protected-span set (mirror of `_PROTECTED_PATTERN`) | shipped |
| G-331 | ci | `.github/workflows/ci.yml:56-57` | D1 | S1 | quality job exports `ATHENA_TERRAFORM_REQUIRED: "1"` + `ATHENA_GO_REQUIRED: "1"` but provisions neither tool — Go survives on the runner image, terraform does not: CI run 38726215232 `test_terraform_apply` failed "terraform CLI is required but was not found" (masked since envs landed `db531ca` 2026-10-10 by the earlier Type-check failure); last green run 36899266699 (2026-10-01) shows the test SKIPPING — terraform was never on the runner; module constraint is `>= 1.5` (`libs/athena-local/tests/terraform/apply/versions.tf`) | `hashicorp/setup-terraform` step before Test in the quality job (pin `@v4.0.1` per the repo's third-party pin convention; `terraform_wrapper: false`) | shipped |

- IDs are sequential `G-NN` repo-wide — next free number is **G-332**
  (G-01…G-325 are dispositioned in `docs/archive/repo-quality/deep-audit/
  gaps.md`; athena-emulator's GP-* register is in
  `docs/archive/athena-emulator/gaps.md`).
- Severity S1–S4 + waived per
  `docs/methodology/deep-audit/methodology.md` §5; a waived row requires a
  written reason.
- A row leaves the register when its fix ships (the measured evidence
  flips) or is waived.
