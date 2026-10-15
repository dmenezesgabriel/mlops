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

- IDs are sequential `G-NN` repo-wide — next free number is **G-329**
  (G-01…G-325 are dispositioned in `docs/archive/repo-quality/deep-audit/
  gaps.md`; athena-emulator's GP-* register is in
  `docs/archive/athena-emulator/gaps.md`).
- Severity S1–S4 + waived per
  `docs/methodology/deep-audit/methodology.md` §5; a waived row requires a
  written reason.
- A row leaves the register when its fix ships (the measured evidence
  flips) or is waived.
