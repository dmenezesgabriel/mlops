# SSG site experience — documentation index

> **ARCHIVED 2026-10-14 — closed workstream (M9 shipped).** The live doc
> set is `docs/` (`README.md` for the index); permanent reference docs are
> `docs/components/ssg/`.

Reader-facing features for the `libs/ssg` built site — the table-stakes
feature set of the two dominant docs frameworks, Material for MkDocs and
Astro Starlight, ranked by default-on evidence in both ecosystems.
Implemented across `libs/ssg`, `libs/ssg-syntax-highlighting`, and
`site/`: heading permalinks, code copy buttons, dark palette + theme
toggle, per-locale search index + header UI, canonical/OG/favicon head
tags, sitemap + robots + 404, print stylesheet, GitHub-alert admonitions,
TOC scrollspy + back-to-top, mobile TOC disclosure, last-updated +
edit-this-page.

## Documentation map

| Path | Kind | Status |
|---|---|---|
| [prd.md](prd.md) | **Ephemeral** — functional requirements FR-11…FR-24, evidence + acceptance | History — never cited from code |
| [backlog.md](backlog.md) | **Ephemeral** — evidence-anchored work items SX-1…SX-14 | History — never cited from code |
| [milestones.md](milestones.md) | **Ephemeral** — M9 ordered steps + exit criteria | History — never cited from code |

Conventions are the live doc set's (`docs/README.md`): evidence citations
are repo-relative `file:line` anchors into the frozen checkouts under
`research_repos/` plus measured numbers; one fact per table row.

## Verified evidence index (most-referenced anchors)

| Topic | Anchor |
|---|---|
| Feature ranking: default-on in both frameworks | `research_repos/mkdocs/mkdocs/config/defaults.py:157` (search default-on); `research_repos/starlight/packages/starlight/src/utils/user-config.ts:194-317` (schema defaults) |
| Search index entry shape `{title,text,location}` + per-section entries | `research_repos/mkdocs/mkdocs/contrib/search/search_index.py:48-53,95,124-125` |
| Search UI / theme select / mobile TOC / last-updated + edit link references | `research_repos/starlight/packages/starlight/src/components/{Search,ThemeSelect,MobileTableOfContents,LastUpdated,EditLink}.astro` (+ `utils/git.ts`) |
| i18n UI strings incl. code-copy labels | `research_repos/starlight/packages/starlight/src/schemas/i18n.ts:232-240` |
| Admonitions + sitemap + print reference impls | `research_repos/starlight/packages/starlight/src/integrations/{remark-asides,sitemap}.ts`, `style/print.css`; `mdit_py_plugins` `admon`/`colon_fence` (venv) |
| sitemap/robots/404 + search-modal reference impls | `research_repos/mkdocs/mkdocs/commands/build.py:109`, `themes/mkdocs/{404.html,search-modal.html}` |
| Implementation surface (ours) | `libs/ssg/src/ssg/application/use_cases/static_site_builder.py`, `infrastructure/{markdown_content_renderer,html_article_outline_builder,jinja_page_renderer,site_config_repository,git_source_revision_provider,i18n_site_variant_provider}.py`, `infrastructure/frontend/templates/` + `templates/partials/`, `static/{css/site.css,js/site.js}`, `site/site.yaml` |
| E2E pin: search + theme + both locales + no-JS degradation | `libs/ssg/tests/playwright/{test_built_site_smoke,test_built_site_print}.py` (9 tests; `site/build` served via ephemeral `ThreadingHTTPServer`) |

## Implementer starting point

Workstream closed — these docs are evidence and history. The component
reference is `docs/components/ssg/ssg.md`; site configuration lives in
`site/site.yaml`.
