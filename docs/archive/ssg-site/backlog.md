# Backlog — SSG site experience (EPHEMERAL)

> **EPHEMERAL — never cited from code.** Shipped work items, kept as
> evidence. One item per row, evidence-anchored, TDD-shaped. Prefix `SX-*`
> is closed — reuse only for this domain.

Reader-facing features for the `libs/ssg` site, benchmarked against
Material for MkDocs (`research_repos/mkdocs-material`, `…/mkdocs`) and
Astro Starlight (`research_repos/starlight`) — ranking evidence is
default-on in both ecosystems; full rationale + inventory in
`prd.md` (FR-11…FR-24). One item = one session,
end-to-end slice (config → build → template/asset → tests). Explicitly
out of scope: instant navigation, versioning, blog, comments, analytics,
feedback widgets, offline mode, generated social-card images, Mermaid —
real census features whose cost doesn't pay on a ~22-page bilingual
portfolio.

| ID | Item | Work | Evidence | Depends |
|---|---|---|---|---|
| SX-1 | [x] Heading permalink affordance: `headerlink` anchor injected by the outline builder (ids already assigned) + hover style; FR-16 | S | starlight `user-config.ts:299` (default true) + `integrations/rehype-heading-links.ts`; ours `infrastructure/html_article_outline_builder.py:13-32`, `article_toc.html` hrefs must match | — |
| SX-2 | [x] Copy button on code blocks: `<pre>` wrapper in the highlighter + `navigator.clipboard` handler + "Copied!" i18n label; FR-15 | S | starlight `schemas/i18n.ts:232-240`; material `content.code.copy`; ours `libs/ssg-syntax-highlighting/…/pygments_highlighter.py`, `static/js/site.js`, i18n `extension_setting` pattern `page.html:23-28` | — |
| SX-3 | [x] Dark palette: CSS custom-prop dark `data-theme` variant + `prefers-color-scheme` default, no FOUC; FR-13 | S | material `docs/setup/changing-the-colors.md`; starlight `ThemeProvider.astro`; measured: zero `prefers-color-scheme` in `static/css/site.css` | — |
| SX-4 | [x] Theme toggle in `header-actions` + `localStorage` + inline FOUC-guard script; FR-14 | S | starlight `ThemeSelect.astro`; ours `partials/header.html:7-38`, `base.html:6` (`data-theme` hook already on `<body>`) | SX-3 |
| SX-5 | [x] `search-index.json` per locale at build: `{title,text,location}` per page + per TOC section; FR-11 | S | mkdocs `contrib/search/search_index.py:48-53,95,124-125`; ours `use_cases/static_site_builder.py`, `domain/entities/article.py` (headings) | — |
| SX-6 | [x] Search UI: header input + results dropdown, lazy-fetch index, ranked client-side filter, Escape closes, works per-locale, playwright smoke; FR-12 | M | starlight `Search.astro`; mkdocs `themes/mkdocs/search-modal.html`; ours `partials/header.html:7-38`, `static/js/site.js`, `tests/playwright/test_built_site_smoke.py` | SX-5 |
| SX-7 | [x] `site.url` + `site.repo_url` config → canonical + OG + favicon tags in `<head>`; FR-17 | S | starlight `user-config.ts:241,263` (head/favicon); mkdocs `commands/build.py:109`; measured absent in `partials/head.html:1-11`; config lands in `site_config_repository.py` + `site/site.yaml` | — |
| SX-8 | [x] `sitemap.xml` + `robots.txt` emitted at build root, per locale; FR-18 | S | mkdocs `commands/build.py:109`; starlight `integrations/sitemap.ts`; ours `use_cases/static_site_builder.py` | SX-7 |
| SX-9 | [x] `404.html` emitted with site chrome; FR-19 | S | mkdocs `themes/mkdocs/404.html`; starlight `user-config.ts:273`; ours `templates/` + `static_site_builder.py` | — |
| SX-10 | [x] Print stylesheet: nav/pager/toc hidden, content full-width; FR-20 | S | starlight `style/print.css:1`; ours `static/css/site.css` | — |
| SX-11 | [x] Admonitions: GitHub-alert `> [!NOTE|TIP|IMPORTANT|WARNING|CAUTION]` in md + notebook cells, i18n labels, callout CSS; FR-21 | M | starlight `integrations/remark-asides.ts` + `user-components/Aside.astro`; material `docs/reference/admonitions.md`; `mdit_py_plugins` already in `.venv` (`admon`, `colon_fence`); ours `markdown_content_renderer.py:64-79` loader + notebook renderer | — |
| SX-12 | [x] TOC scrollspy (`aria-current`) + back-to-top button; FR-22 | S | material `toc.follow`/`navigation.top` (`setting-up-navigation.md:451,498`); starlight `TableOfContents.astro`; ours `site.js:13-27` IntersectionObserver precedent, `partials/article_toc.html` | — |
| SX-13 | [x] Mobile TOC `<details>` at article top, visible ≤58rem; FR-23 | S | starlight `MobileTableOfContents.astro`; ours `partials/article_toc.html` + `page.html:19-35`, breakpoint `site.css:540` | — |
| SX-14 | [x] Last-updated (git log per page source) + edit-this-page link; FR-24 | M | starlight `LastUpdated.astro`/`EditLink.astro` + `utils/git.ts` degrade-to-omit; ours `ports/source_revision_provider.py`, `infrastructure/git_source_revision_provider.py`, `static_site_builder.py:370,404-417`, `partials/page_meta.html` + `page.html:35`, `Page.original_source_path` provenance, `site.edit_base_url`/`last_updated` in `site_config_repository.py:40-44`, i18n labels via `i18n_site_variant_provider.py` | SX-7 |

## Definition of Done (all items)

- Evidence cell cites `file:line` or measured numbers — never "should".
- TDD where behavior changes: failing test first; pure refactors keep
  existing tests green.
- Gates green for the touched package (`make quality`), numbers recorded
  in the commit body.
- Item box checked in the same commit; owning milestone step updated.
