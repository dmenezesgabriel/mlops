# Milestones — SSG site experience (EPHEMERAL)

> **EPHEMERAL — never cited from code.** Shipped phase, kept as evidence.

## M9 — ssg site experience (backlog SX-*)

Goal: the `libs/ssg` built site carries the table-stakes reader features
of the two dominant docs frameworks — Material for MkDocs and Astro
Starlight — ranked by default-on evidence (mkdocs `config/defaults.py:157`;
starlight `utils/user-config.ts:194-317`). Scope + per-feature evidence in
`prd.md` (FR-11…FR-24); out-of-scope list in `backlog.md`'s intro.

Steps:
1. [x] Heading permalink affordance (SX-1)
   - Evidence: starlight `utils/user-config.ts:299`; `infrastructure/html_article_outline_builder.py:13-32`
2. [x] Copy button on code blocks (SX-2)
   - Evidence: starlight `schemas/i18n.ts:232-240`; `libs/ssg-syntax-highlighting/…/pygments_highlighter.py`
3. [x] Dark palette + `prefers-color-scheme` (SX-3)
   - Evidence: measured zero `prefers-color-scheme` in `static/css/site.css`
4. [x] Theme toggle + persistence + FOUC guard (SX-4)
   - Evidence: starlight `ThemeSelect.astro`; `base.html:6` `data-theme` hook
5. [x] `search-index.json` per locale (SX-5)
   - Evidence: mkdocs `contrib/search/search_index.py:48-53,124-125`
6. [x] Search UI + playwright smoke (SX-6)
   - Evidence: starlight `Search.astro`; `partials/header.html:7-38`
7. [x] `site.url`/`site.repo_url` → canonical + OG + favicon (SX-7)
   - Evidence: starlight `user-config.ts:241,263`; `partials/head.html:1-11`
8. [x] `sitemap.xml` + `robots.txt` (SX-8)
   - Evidence: mkdocs `commands/build.py:109`
9. [x] `404.html` (SX-9)
   - Evidence: mkdocs `themes/mkdocs/404.html`
10. [x] Print stylesheet (SX-10)
    - Evidence: starlight `style/print.css:1`
11. [x] GitHub-alert admonitions in md + notebook cells (SX-11)
    - Evidence: starlight `integrations/remark-asides.ts`; `mdit_py_plugins` `admon`/`colon_fence` in `.venv`
12. [x] TOC scrollspy + back-to-top (SX-12)
    - Evidence: material `setting-up-navigation.md:451,498`; `site.js:13-27`
13. [x] Mobile TOC `<details>` (SX-13)
    - Evidence: starlight `MobileTableOfContents.astro`; `site.css:540`
14. [x] Last-updated + edit-this-page (SX-14)
    - Evidence: starlight `LastUpdated.astro`/`EditLink.astro` + `utils/git.ts`; ours `infrastructure/git_source_revision_provider.py`, `partials/page_meta.html`

**Exit criteria:** `make quality` green for `libs/ssg` +
`libs/ssg-syntax-highlighting`; `make build-site` emits
`search-index.json` per locale, `sitemap.xml`, `robots.txt`, `404.html`;
playwright smoke covers search + theme toggle; every feature works in
both locales and degrades without JS.

## Sequence & dependencies

M9 standalone — touched `libs/ssg`(+`-syntax-highlighting`) and `site/`
only. All SX items independent except SX-4→SX-3, SX-6→SX-5, SX-8→SX-7,
SX-14→SX-7; steps ordered quick-wins first, search slice mid-milestone,
SEO slice before the dependent freshness item.
