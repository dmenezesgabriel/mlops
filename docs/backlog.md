# Backlog (EPHEMERAL)

> **EPHEMERAL — iterates; never cited from code.** One work item per row,
> evidence-anchored, TDD-shaped. Group rows under a lettered section per
> workstream/domain; each section header declares its ID prefix. Prefixes
> from closed workstreams (QC/SP/PC/MD/QE/AR/CS/DP/NB/GF/QA, MQ/QH,
> AU/AF/AX, SX) live in `docs/archive/` — reuse a prefix only for the same
> domain. Work sizes: S ≤ 1 day · M = 1–3 days · L = 3–5 days.

## A. SSG site phase 2 — deferred census features + mobile responsiveness (SX-15…22)

Same domain as the archived M9 workstream
(`docs/archive/ssg-site/backlog.md`), so the `SX-*` prefix continues per
the header rule. Rows reinstate the M9 out-of-scope cut where the user
picked it up — that intro listed instant navigation, versioning, blog,
comments, analytics, feedback widgets, offline mode, generated
social-card images, Mermaid; still out: comments, analytics, feedback
widgets. Requirements `prd.md` FR-25…32; ordering + exit gate
`milestones.md` M10. One item = one session, end-to-end slice
(config → build → template/asset → tests).

| ID | Item | Work | Evidence | Depends |
|---|---|---|---|---|
| SX-15 | [x] done 2026-10-15 — playwright sweep 320/390/768px × index/article-with-table/code/notebook/404 × en+pt-BR asserting zero horizontal overflow, ≥44px tap targets, inputs ≥16px, nav/search/TOC reachable (13 tests); measured+fixed: pt-BR 320px header overflow (hid `.language-switcher__label`, capped `.theme-select`/`.search-input` under 40rem), `.theme-select`+`.mobile-toc summary` tap floors (`min-height: 2.75rem` under 58rem), 12.8px `.search-input`/`.theme-select` fonts (→1rem), 13px widget `<select>` (`!important` in `.jupyter-widgets-container`); FR-25; clears G-326…328 + G-333…335 | M | ours `tests/playwright/test_built_site_responsive.py` + `site.css:236,254` (1rem controls), `:783` (44px floor), `:795-802` (320px compaction), `:644-648` (widget font); 404 absolute-asset redirect `test_built_site_responsive.py:8,99-109` | — |
| SX-16 | [x] done 2026-10-15 — `site.image` config → `Site.image`, copied per variant to `assets/`; `AlternateLink` VO + `alternate_links_for` emit absolute per-locale `rel="alternate"` + `x-default`; `head.html` adds `twitter:card`/`twitter:title`/`twitter:description`/`twitter:image` + `og:image` gated on `site.url`; real `make build-site` heads verified en+pt-BR (`<url>/` vs `<url>/pt-BR/`); FR-26 | S | ours `domain/value_objects/alternate_link.py` + `partials/head.html` + `use_cases/static_site_builder.py` `_write_assets`; playwright `tests/playwright/test_built_site_seo.py` (2 tests); gates: ssg `make quality` green (99.57% cov, 308 tests), ssg-i18n green (99.78%, 160), playwright suite 23 green; ref starlight `src/utils/head.ts:70,80-101` | — |
| SX-17 | [x] done 2026-10-15 — new `libs/ssg-mermaid` plugin package (ssg-latex parity): `MermaidHtmlPostProcessor` claims `pre>code.language-mermaid`/`pre.mermaid` blocks → `SubprocessMermaidRenderer` → vendored `render.mjs` (mermaid@11.17.2 + svgdom + jsdom + dompurify, `npm ci` provisioned on first use) emits inline SVG carrying `var(--surface)`/`--ink` themeCSS (follows light/dark switch live); chose build-time over material's runtime mermaid.js — static-site convention, no-JS diagram already drawn; new `ssg.early_html_post_processors` group loads before `ssg.html_post_processors` so mermaid wins the `language-mermaid` race vs pygments; `.mermaid-diagram` joins the framed-media CSS rule; FR-27 | M | ours `libs/ssg-mermaid/` (processor/parser/subprocess/render.mjs) + `cli.py:188-211` two-phase loader; `make build-site` verified inline svg en+pt-BR problem-framing; unit 24 (99.51% cov) + cli group-ordering tests + playwright `test_built_site_mermaid.py` (4 tests incl. palette light/dark + 320px); gates: ssg-mermaid `make quality` green, ssg `make quality` green (99.55% cov, 308 tests), e2e 28 green, `lint-imports` green; limitation: gantt-type diagrams fail the build (no browser layout metrics server-side) | — |
| SX-18 | [ ] Instant navigation: internal-link prefetch + content swap, re-init search/theme/scrollspy post-swap; FR-30 | M | material `docs/setup/setting-up-navigation.md:26-68` (`navigation.instant`, `.prefetch`, needs `site_url` — set at `site/site.yaml:4`), impl `src/templates/assets/javascripts/integrations/instant/index.ts`; ours `static/js/site.js` | — |
| SX-19 | [ ] Offline mode: build-id-versioned service worker precaches pages + assets per locale; playwright offline smoke; FR-29 | M | material `src/plugins/offline/plugin.py` (offline build + SW); ours emit `sw.js` + register from `static/js/site.js`, emitted by `use_cases/static_site_builder.py` | SX-18 |
| SX-20 | [ ] Generated social cards: per-page `og:image` rendered at build (page title + site chrome); FR-28 | L | material `src/plugins/social/` (`plugin.py`, `layout.py`, `templates/default.yml:171-181` og:image/twitter:image); needs SX-16's `og:image` emission | SX-16 |
| SX-21 | [ ] Versioning: versioned output layout + header switcher + `latest` alias; canonical/sitemap/hreflang per version; FR-31 | L | material `docs/setup/setting-up-versioning.md:18-25` (mike — external tool, not vendored; ours reimplements the layout); ours `use_cases/static_site_builder.py` output layout + `partials/header.html` | SX-16 |
| SX-22 | [ ] Blog: dated-posts collection type + index + RSS feed + author/readtime; FR-32 | L | material `src/plugins/blog/` (`plugin.py`, `author.py`, `structure/`, `readtime/`); ours `collections` config `site/site.yaml` + index templates | — |

## B. Fix items (AF-176…179)

| ID | Item | Work | Evidence | Depends |
|---|---|---|---|---|
| AF-176 | [x] done 2026-10-15 — `children` walk now guards present-`None` (`getattr(...) or []` into a `list[object]` binding, strict-pyright-clean); +2 parametrized regression tests (ThematicBreak/CodeFence verified RED with the production traceback); G-329 | S | traceback measured on real docs 2026-10-15 (`TypeError: 'NoneType' object is not iterable` at `application/use_cases/machine_translation_evaluator.py:71`); translator's guard `document_translator.py:337-338`; own `render_node` guard `:83` | — |
| AF-177 | [x] done 2026-10-15 — `is_fallback` now requires letters after stripping `_PROTECTED_SPAN_PATTERN` (mirror of `_PROTECTED_PATTERN` minus the MATHEXPR arm); real `make evaluate-translation` re-run: fallback 19→11 (12.34%→7.14% < 8% gate), BLEU 43.74 > 40 — PASSED; +2 regression tests (math-only/directive-only RED-verified); G-330 | S | real eval 2026-10-15: 12.34% flagged vs true ≈7.1%; protected set `document_translator.py:97-101` (`_PROTECTED_PATTERN`) + `:280-291` math placeholders; flag site `machine_translation_evaluator.py:97-101` | AF-176 |
| AF-178 | [x] done 2026-10-15 — `hashicorp/setup-terraform@v4.0.1` step added before the compose stack in the quality job (`terraform_wrapper: false` — the test harness shells out to the real binary); G-331 | S | CI run 38726215232 Quality Gates Test log; env exports `ci.yml:56-57`; constraint `libs/athena-local/tests/terraform/apply/versions.tf` `>= 1.5`; green-run skip evidence 36899266699 | — |
| AF-179 | [x] done 2026-10-15 — two complementary fixes: `max_new_tokens` now budgets by input chars (word-count under-served ~12-token markers), and `_heal_mangled_marker` gained an index-anchored remnant pass (`TR{n}`/`MATHEXPR{n}` + `X` + ≥2-hex tail, no leading `\b` for glued markers); real regen + eval: fallback 11→6 (3.9%), BLEU 43.74, PASSED; +5 regression tests (3 heal shapes + unidentifiable-remnant guard + char-budget pin); G-332 | M | instrumented run 2026-10-15: 13/68 marker calls reverted, dominant mode = token-budget truncation at output end; revert site `document_translator.py:502-503`; budget/heal sites `transformers_text_translator.py:52-58`, `document_translator.py:128-149`; residual 6 = technical-term echoes + 2 full drops (revert correct — unidentifiable remnant) | AF-178 |

Closed sections (archived 2026-10-14):
A. Athena emulator showcase notebooks (NB-7…16) →
`docs/archive/athena-emulator/backlog.md` §L · B. SSG site experience
(SX-1…14) → `docs/archive/ssg-site/backlog.md` · C. Fix items (AF-175) →
`docs/archive/repo-quality/deep-audit/backlog.md` §D.

## Definition of Done (all items)

- Evidence cell cites `file:line` or measured numbers — never "should".
- TDD where behavior changes: failing test first; pure refactors keep
  existing tests green.
- Gates green for the touched package (`make quality`), numbers recorded
  in the commit body.
- Item box checked in the same commit; owning milestone step updated.
