# PRD (EPHEMERAL)

> **EPHEMERAL — never cited from code.** Functional requirements for the
> active scope, in per-domain tables. One row per requirement: evidence +
> acceptance, never prose. Requirements of shipped workstreams live in
> `docs/archive/`.

## athena_emulator showcases

Scope: `projects/athena_emulator/notebooks/` — nine scenario-driven usage
showcase notebooks, one per real-world consumer flow, each persisting
measured rows to `parity/<stem>.md`. Who else implements it: awswrangler's tutorial
series (`research_repos/aws-sdk-pandas/tutorials/006 - Amazon Athena.ipynb`)
is the style reference; the CLI's shipped `.rst` examples
(`research_repos/aws-cli/awscli/examples/athena/`, 28 files) are the ops
inventory; `libs/athena-local/tests/terraform/apply/main.tf` is the IaC
reference. Implementation inventory: `notebooks/*.ipynb`,
`notebooks/_evidence.py:60-108`, `notebooks/_helpers.py`,
`tests/test_notebooks.py:111-143,286-294`, `parity/`, `PARITY.md`.

| ID | Requirement | Evidence / who else implements it | Acceptance | Gap |
|---|---|---|---|---|
| FR-1 | `01_quickstart.ipynb` — first-query showcase: endpoint split, boto3 SELECT round-trip, result artifacts on S3, wrangler one-liner | `projects/athena_emulator/PARITY.md` §01 (4 PASS) | nbclient-executed outputs committed; `parity/01_quickstart.md` persisted | complete |
| FR-2 | `02_analytics_dataframes.ipynb` — analyst reads: csv/ctas/api `read_sql_query`, cache, chunksize, categories, dtype_backend, named+qmark params, table/result/execution/schema helpers | `PARITY.md` §04 (30 PASS); `_read.py:209-238` csv contract | executes clean; `parity/02_analytics_dataframes.md` | complete |
| FR-3 | `03_data_engineering.ipynb` — lake writes/DDL: partitioned datasets, CTAS, UNLOAD, `repair_table`, external tables, `SHOW PARTITIONS`/`$partitions`, `store_parquet_metadata`, delete flows | `PARITY.md` §04/§05; CTAS `_utils.py:860-872` | executes clean; `parity/03_data_engineering.md` | complete |
| FR-4 | `04_app_integration.ipynb` — service-side lifecycle: poll/cancel/pagination, named queries, prepared statements + `EXECUTE`/`USING`, `ClientRequestToken` dedupe, `ResultReuseConfiguration`, runtime statistics | `PARITY.md` §03 (21 PASS); ADR-0009 | executes clean; `parity/04_app_integration.md` | complete |
| FR-5 | `05_governance.ipynb` — platform admin: workgroup CRUD/enforced/fallback/managed/disabled, `BytesScannedCutoff`, tags, data catalogs, engine versions, encryption echo | `PARITY.md` §02 (15 PASS) + §03 encryption row | executes clean; `parity/05_governance.md` | complete |
| FR-6 | `06_iceberg_tables.ipynb` — `to_iceberg` + `delete_from_iceberg_table` row-delete usage | `PARITY.md` §05 iceberg rows; `test_iceberg_consumer.py`; ADR-0013 | executes clean; `parity/06_iceberg_tables.md` | complete |
| FR-7 | `07_aws_cli.ipynb` — `aws athena … --endpoint-url` ops over the shipped `.rst` example inventory | `examples/athena/` 28 files; `test_aws_cli_consumer.py`; `_cli_examples.py`; `.venv/bin/aws` (awscli 1.46.1) | executes clean; `parity/07_aws_cli.md` | complete |
| FR-8 | `08_terraform_iac.ipynb` — `init→apply→plan→destroy` over the 5 `aws_athena_*` resources | `tests/terraform/apply/main.tf:35,52,58,66,73` + `.plugin-cache/`; `test_terraform_apply.py`; `_terraform_harness.py:96,108`; socket `docker-compose.yml:102` | executes clean; `parity/08_terraform_iac.md` | complete |
| FR-9 | `09_boundaries.ipynb` — error taxonomy + out-of-scope ops returning shaped `InvalidRequestException` | `PARITY.md` §02/§03/§05 error rows; ADR-0004; `test_query_error_mapping.py` | executes clean; `parity/09_boundaries.md` | complete |
| FR-10 | Evidence machinery kept: `record()`/`persist()` → `parity/`/`PARITY.md`; test hook's fragment + zero-FAIL invariants unchanged; matrices framed as capabilities demonstrated | `_evidence.py:60-108`; `test_notebooks.py:117-143,286-294`; `Makefile:18` coverage floor 95 | `make quality` green at every item commit | complete |

Row rules (prompt-execution §3): every row cites verified `file:line`
paths or measured numbers; where references disagree, name the
disagreement — it is the decision the implementing item must make. Add a
gap column when comparing against reference implementations: absent /
partial / complete.

## ssg site experience

Scope: `libs/ssg` + `libs/ssg-syntax-highlighting` + `site/` — reader-facing
site features benchmarked against the two dominant docs frameworks:
Material for MkDocs (~27.2k stars, ~11.7M PyPI downloads/mo) at
`research_repos/mkdocs-material` + `research_repos/mkdocs`, and Astro
Starlight (~9k stars, ~1.45M npm downloads/wk) at `research_repos/starlight`.
Ranking evidence = default-on in both ecosystems (mkdocs
`config/defaults.py:157` search default; starlight
`utils/user-config.ts:194-317` schema defaults). Implementation inventory:
`libs/ssg/src/ssg/application/use_cases/static_site_builder.py`,
`infrastructure/{markdown_content_renderer,html_article_outline_builder,jinja_page_renderer,site_config_repository,local_preview_server}.py`,
`infrastructure/frontend/templates/{base,index,page}.html`,
`templates/partials/{head,header,navigation,article_toc,pager,footer,collection_card}.html`,
`templates/fragments/`, `static/{css/site.css,js/site.js}`, `site/site.yaml`.

| ID | Requirement | Evidence / who else implements it | Acceptance | Gap |
|---|---|---|---|---|
| FR-11 | Build emits `search-index.json` per locale: `{title,text,location}` per page + per TOC section | mkdocs `contrib/search/search_index.py:48-53,95,124-125` (entry shape, section entries, lunr `ref/fields`); search is default-on (`config/defaults.py:157`); starlight pagefind auto-on (`utils/user-config.ts:265-270,310-313`) | index file in `site/build/` per locale; unit test pins schema | absent |
| FR-12 | Header search UI: input + results dropdown, lazy-fetches index, client-side filter, Escape closes, no-JS page still works | starlight `components/Search.astro` (Pagefind); mkdocs theme `themes/mkdocs/search-modal.html`; our `partials/header.html:7-38`, `static/js/site.js` | type query → ranked links; playwright smoke covers it | complete |
| FR-13 | Dark palette: CSS custom-prop dark `data-theme` variant, `prefers-color-scheme` default | material `docs/setup/changing-the-colors.md` (`palette.scheme`); starlight `components/ThemeProvider.astro`; measured gap: zero `prefers-color-scheme` in `static/css/site.css` (637 lines) | dark renders without toggle; no flash on load | complete |
| FR-14 | Theme toggle in header: explicit choice persists (`localStorage`), inline FOUC guard | starlight `components/ThemeSelect.astro`; material palette toggle; our `partials/header.html:7-38` | toggle flips theme, survives reload | complete |
| FR-15 | Copy button on rendered code blocks + "Copied!" feedback, i18n label | starlight `schemas/i18n.ts:232-240` (EC copy strings, build-time injection); material `content.code.copy` + runtime injection (`templates/clipboard/index.tsx:37-46`, support-gated); ours `CodeBlockSyntaxHighlightingProcessor._copy_button_markup` + `CodeBlockHtmlParser` emit `.code-frame` + button (`libs/ssg-syntax-highlighting/.../application/syntax_highlighter.py`), `static/js/site.js` clipboard handler | button on every fenced block; clipboard write verified in test | complete |
| FR-16 | Heading permalink affordance (hover/click link to `#id`) | starlight `markdown.headingLinks` default true (`user-config.ts:299`) + `integrations/rehype-heading-links.ts`; our `html_article_outline_builder.py:13-32` already assigns `id`s + `ArticleHeading` | every rendered heading self-links; href matches TOC | complete |
| FR-17 | `site.url` config → canonical + Open Graph + favicon tags in `<head>` | starlight `head` config (`user-config.ts:241`) + `components/Head.astro`, `favicon` (`user-config.ts:263`); material social plugin `src/plugins/social`; measured gap: built `<head>` has none (`partials/head.html:1-11`) | built pages carry canonical/og/favicon tags | absent |
| FR-18 | `sitemap.xml` + `robots.txt` emitted at build | mkdocs `commands/build.py:109` (sitemap template); starlight `integrations/sitemap.ts` (@astrojs/sitemap) | both files at build root; URLs use `site.url` | absent |
| FR-19 | `404.html` emitted at build | mkdocs default theme ships `themes/mkdocs/404.html`; starlight built-in (`disable404Route`, `user-config.ts:273`) | `site/build/404.html` renders with site chrome | absent |
| FR-20 | Print stylesheet: nav/pager/toc hidden, content full-width | starlight `style/print.css:1` (`@media print`) | `@media print` block in `site.css`; print preview clean | absent |
| FR-21 | Admonitions via GitHub-alert syntax `> [!NOTE|TIP|WARNING|…]`, i18n labels | starlight `integrations/remark-asides.ts` + `user-components/Aside.astro`; material `docs/reference/admonitions.md`; `mdit_py_plugins` already pinned (`admon`, `colon_fence` in `.venv`); loader pattern `markdown_content_renderer.py:64-79` | alerts render as styled callouts in md + notebook cells | absent |
| FR-22 | TOC scrollspy (`aria-current` on visible section) + back-to-top | material `toc.follow`/`navigation.top` (`docs/setup/setting-up-navigation.md:451,498`); starlight `TableOfContents.astro`; IntersectionObserver precedent `static/js/site.js:13-27` | TOC highlights current section on scroll | partial |
| FR-23 | Mobile TOC: `<details>` at article top under 58rem breakpoint | starlight `components/MobileTableOfContents.astro`; our `partials/article_toc.html`, `site.css:540` | TOC reachable on mobile | partial |
| FR-24 | Last-updated date (git log per source) + edit-this-page link (`site.repo_url`) | starlight `LastUpdated.astro`/`EditLink.astro` + `user-config.ts:200,261`; material git-revision-date plugin | footer shows date + link per page | absent |
