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
| FR-25 | Responsive pass: no horizontal overflow, ≥16px input font (no iOS auto-zoom), ≥44px tap targets, nav/search/TOC reachable at 320/390/768px on every page type | starlight mobile-first breakpoints 50/72rem (`src/style/props.css:176,187`, `src/style/util.css:23,34`); ours `site.css:773,784` (58/40rem) only; suspects `site.css:247-255` (`.search-input` 0.8rem), `:215-226` (`.menu-toggle`); coverage `tests/playwright/test_built_site_smoke.py:222,554` pins 390px menu/TOC only | playwright sweep green at 320/390/768px × index/article/404 | partial |
| FR-26 | SEO extras: `twitter:card`/`twitter:title`/`twitter:description`/`twitter:image` + `rel="alternate"` hreflang per locale + `x-default` + static site image → `og:image` | starlight `src/utils/head.ts:70` (twitter:card), `:80-101` (hreflang alternates + x-default), `:116-122` (twitter:site), `head` config extension `src/utils/user-config.ts:100-119,241`; material `src/plugins/social/templates/default.yml:178-181`; measured absent `partials/head.html:1-25`; `site.url` set `site/site.yaml:4`; locales `en,pt-BR` `site/site.yaml:11` | built `<head>` carries twitter:* block, per-locale alternates + x-default, og:image | partial |
| FR-27 | ` ```mermaid ` fenced blocks render as diagrams | material `docs/reference/diagrams.md:20-28` (superfences `name: mermaid` custom fence + mermaid.js runtime); ours `markdown_content_renderer.py:65-82` plugin loader — no mermaid handling (grep-verified); decision the item makes: runtime mermaid.js (material way) vs build-time render under the site's no-JS-degrade convention | mermaid fence → diagram; degrades to a readable block without JS | absent |
| FR-28 | Generated social cards: per-page `og:image` rendered at build | material `src/plugins/social/` (`plugin.py`, `layout.py`, `templates/default.yml:171-181` og:image/twitter:image shapes); emission path lands in FR-26 | per-page image emitted in build + `<head>` resolves it | absent |
| FR-29 | Offline mode: build-id-versioned service worker precaches pages + assets per locale | material `src/plugins/offline/plugin.py` (offline build + SW); ours `static/js/site.js` registration site, `use_cases/static_site_builder.py` emitter | playwright `context.set_offline` → built pages still load | absent |
| FR-30 | Instant navigation: internal-link prefetch + content swap | material `docs/setup/setting-up-navigation.md:26-68` (`navigation.instant`, `.prefetch`, `site_url` requirement), impl `src/templates/assets/javascripts/integrations/instant/index.ts`; ours `static/js/site.js` | in-site navigation swaps content; search/theme/scrollspy re-init post-swap | absent |
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
