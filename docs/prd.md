# PRD (EPHEMERAL)

> **EPHEMERAL — never cited from code.** Functional requirements for the
> active scope, in per-domain tables. One row per requirement: evidence +
> acceptance, never prose. Requirements of shipped workstreams live in
> `docs/archive/`.

## Active scope: ssg site phase 2

`libs/ssg` + `site/` reader-facing features — continuation of the archived
M9 census (`docs/archive/ssg-site/prd.md`; same two references: Material
for MkDocs `research_repos/mkdocs-material`, Astro Starlight
`research_repos/starlight`). Reinstates part of the M9 out-of-scope cut
(`archive/ssg-site/backlog.md` intro) plus a measured
mobile-responsiveness pass. Still out: comments, analytics, feedback
widgets. Ships via `backlog.md` §A (SX-15…22), phased in `milestones.md`
M10.

| ID | Requirement | Evidence / who else implements it | Acceptance | Gap |
|---|---|---|---|---|
| FR-25 | Responsive pass: no horizontal overflow, ≥16px input font (no iOS auto-zoom), ≥44px tap targets, nav/search/TOC reachable at 320/390/768px on every page type | ours `tests/playwright/test_built_site_responsive.py` (320/390/768 × index/article-table/code/notebook/404 × en+pt-BR) + `site.css:236,254` (1rem), `:783` (44px), `:795-802` (320px compaction), `:644-648` (widget font); starlight mobile-first breakpoints `src/style/props.css:176,187` | playwright sweep green at 320/390/768px × index/article/404 | complete |
| FR-26 | SEO extras: `twitter:card`/`twitter:title`/`twitter:description`/`twitter:image` + `rel="alternate"` hreflang per locale + `x-default` + static site image → `og:image` | ours `partials/head.html` + `domain/value_objects/alternate_link.py` + `tests/playwright/test_built_site_seo.py` (en+pt-BR); starlight `src/utils/head.ts:70` (twitter:card), `:80-101` (hreflang alternates + x-default), `head` config `src/utils/user-config.ts:100-119,241`; material `src/plugins/social/templates/default.yml:178-181`; `site.image` set `site/site.yaml:6`; locales `en,pt-BR` `site/site.yaml:12` | built `<head>` carries twitter:* block, per-locale alternates + x-default, og:image | complete |
| FR-27 | ` ```mermaid ` fenced blocks render as diagrams | ours `libs/ssg-mermaid/` (`application/mermaid_processor.py` parser + `infrastructure/subprocess_renderer.py` + `src/ssg_mermaid/render.mjs` — mermaid@11.17.2+svgdom+jsdom+dompurify vendored via `npm ci`); `cli.py:188-211` `ssg.early_html_post_processors` phase before `ssg.html_post_processors`; `tests/playwright/test_built_site_mermaid.py` (en+pt-BR svg, light/dark palette, 320px); material `docs/reference/diagrams.md:20-28` reference — chose build-time svg over its runtime mermaid.js | mermaid fence → inline SVG at build; already drawn without JS (exceeds degrade criterion); invalid sources fail the build | complete |
| FR-28 | Generated social cards: per-page `og:image` rendered at build | material `src/plugins/social/` (`plugin.py`, `layout.py`, `templates/default.yml:171-181` og:image/twitter:image shapes); emission path lands in FR-26 | per-page image emitted in build + `<head>` resolves it | absent |
| FR-29 | Offline mode: build-id-versioned service worker precaches pages + assets per locale | material `src/plugins/offline/plugin.py` (offline build + SW); ours `static/js/site.js` registration site, `use_cases/static_site_builder.py` emitter | playwright `context.set_offline` → built pages still load | absent |
| FR-30 | Instant navigation: internal-link prefetch + content swap | ours `static/js/instant.js` (sitemap-gated intercept + head-diff swap + prefetch) + `static/js/site.js` (`ssg:navigated` remounts) + `tests/playwright/test_built_site_instant.py` (en+pt-BR); material `docs/setup/setting-up-navigation.md:26-68` + impl `src/templates/assets/javascripts/integrations/instant/index.ts` — locs relativized against the root loc (its host rewrite can't bridge a path-prefixed `site.url`); anchors stay native | in-site navigation swaps content; search/theme/scrollspy re-init post-swap | complete |
| FR-31 | Versioning: versioned output layout + header switcher + `latest` alias | material `docs/setup/setting-up-versioning.md:18-25` (mike provider — mike is external, not vendored; ours reimplements the layout); ours `use_cases/static_site_builder.py` URL layout, `partials/header.html` | versioned paths build; switcher lists versions; canonical/sitemap/hreflang per version | absent |
| FR-32 | Blog: dated-posts collection type + index + RSS feed + author/readtime | material `src/plugins/blog/` (`plugin.py`, `author.py`, `structure/`, `readtime/`); ours `collections` pipeline `site/site.yaml` + index templates | dated posts render + index; RSS emitted per locale | absent |

Row rules (prompt-execution §3): every row cites verified `file:line`
paths or measured numbers; where references disagree, name the
disagreement — it is the decision the implementing item must make. Add a
gap column when comparing against reference implementations: absent /
partial / complete.

Shipped requirement tables (archived 2026-10-14):
athena_emulator showcases FR-1…10 → `docs/archive/athena-emulator/prd.md`
§7 · ssg site experience FR-11…24 → `docs/archive/ssg-site/prd.md`.
