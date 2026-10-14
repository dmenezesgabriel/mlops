# Milestones (EPHEMERAL)

> **EPHEMERAL — iterates; never cited from code.** Ordered phases; steps
> reference `backlog.md` IDs. Each milestone's exit gate = repo quality
> gates green (per-package `make quality` + pre-commit) plus the
> milestone's own exit criteria. Closed phases (athena-emulator M0–M7,
> gate-parity MQ-0…3, deep-audit MA-0…8) live in `docs/archive/`.

## M8 — athena_emulator showcase notebooks (backlog NB-*)

Goal: `projects/athena_emulator/notebooks/` reads as scenario-driven usage
showcases — one notebook per real-world consumer flow — with every
demonstrated feature measured green in its committed `parity/<stem>.md`
fragment (the `record()`/`persist()` machinery is kept, reframed as
capabilities demonstrated).

Steps:
1. [x] Style contract + `01_quickstart.ipynb`; removes `01_smoke_and_endpoints.ipynb` (NB-7)
   - Evidence: `projects/athena_emulator/PARITY.md` §01 (4 PASS); `research_repos/aws-sdk-pandas/tutorials/006 - Amazon Athena.ipynb`
2. [x] `02_analytics_dataframes.ipynb`; removes `02_boto3_control_plane.ipynb` (NB-8)
   - Evidence: `PARITY.md` §04 (28 PASS); `libs/athena-local/tests/integration/test_awswrangler_consumer.py`
3. [x] `03_data_engineering.ipynb`; removes `03_boto3_query_lifecycle.ipynb` (NB-9)
   - Evidence: `PARITY.md` §04/§05 write+DDL rows; `test_unload_consumer.py`, `test_external_table.py`, `test_alter_add_partition.py`
4. [x] `04_app_integration.ipynb`; removes `04_wrangler_read_paths.ipynb` (NB-10)
   - Evidence: `PARITY.md` §03 (21 PASS); `test_prepared_execution.py`, `test_result_reuse.py`, `test_named_queries.py`
5. [x] `05_governance.ipynb`; removes `05_wrangler_write_catalog_and_gaps.ipynb` (NB-11)
   - Evidence: `PARITY.md` §02 (15 PASS); `test_workgroups.py`, `test_tags.py`, `test_data_catalogs.py`
6. [x] `06_iceberg_tables.ipynb` (NB-12)
   - Evidence: `PARITY.md` §05 iceberg rows; `test_iceberg_consumer.py`; `docs/adr/0013-iceberg-via-dedicated-trino-catalog-and-glue-marker-routing.md`
7. [x] `07_aws_cli.ipynb` (NB-13)
   - Evidence: `research_repos/aws-cli/awscli/examples/athena/` (28 `.rst`); `libs/athena-local/tests/integration/test_aws_cli_consumer.py`
8. [x] `08_terraform_iac.ipynb` (NB-14)
   - Evidence: `libs/athena-local/tests/terraform/apply/main.tf` (5 `aws_athena_*` resources); `test_terraform_apply.py`; `_terraform_harness.py:96,108`
9. [x] `09_boundaries.ipynb` (NB-15)
   - Evidence: `PARITY.md` §02/§03/§05 error rows; `docs/adr/0004-studio-apis-out-of-scope.md`
10. [x] Close-out — README re-describe, dead helpers trimmed, full re-execute (NB-16)
    - Evidence: `projects/athena_emulator/README.md`; `projects/athena_emulator/tests/test_notebooks.py:117-143`

**Exit criteria:** `cd projects/athena_emulator && make quality` green AND
`uv run pytest projects/athena_emulator/tests -m integration` re-executes all
nine showcase notebooks against the live stack — zero FAIL rows committed in
`PARITY.md`.

## M9 — ssg site experience (backlog SX-*)

Goal: the `libs/ssg` built site carries the table-stakes reader features
of the two dominant docs frameworks — Material for MkDocs and Astro
Starlight — ranked by default-on evidence (mkdocs `config/defaults.py:157`;
starlight `utils/user-config.ts:194-317`). Scope + per-feature evidence in
`docs/prd.md` §ssg site experience (FR-11…FR-24); out-of-scope list in
`docs/backlog.md` §B.

Steps:
1. [x] Heading permalink affordance (SX-1)
   - Evidence: starlight `utils/user-config.ts:299`; `infrastructure/html_article_outline_builder.py:13-32`
2. [x] Copy button on code blocks (SX-2)
   - Evidence: starlight `schemas/i18n.ts:232-240`; `libs/ssg-syntax-highlighting/…/pygments_highlighter.py`
3. [x] Dark palette + `prefers-color-scheme` (SX-3)
   - Evidence: measured zero `prefers-color-scheme` in `static/css/site.css`
4. [ ] Theme toggle + persistence + FOUC guard (SX-4)
   - Evidence: starlight `ThemeSelect.astro`; `base.html:6` `data-theme` hook
5. [ ] `search-index.json` per locale (SX-5)
   - Evidence: mkdocs `contrib/search/search_index.py:48-53,124-125`
6. [ ] Search UI + playwright smoke (SX-6)
   - Evidence: starlight `Search.astro`; `partials/header.html:7-38`
7. [ ] `site.url`/`site.repo_url` → canonical + OG + favicon (SX-7)
   - Evidence: starlight `user-config.ts:241,263`; `partials/head.html:1-11`
8. [ ] `sitemap.xml` + `robots.txt` (SX-8)
   - Evidence: mkdocs `commands/build.py:109`
9. [ ] `404.html` (SX-9)
   - Evidence: mkdocs `themes/mkdocs/404.html`
10. [ ] Print stylesheet (SX-10)
    - Evidence: starlight `style/print.css:1`
11. [ ] GitHub-alert admonitions in md + notebook cells (SX-11)
    - Evidence: starlight `integrations/remark-asides.ts`; `mdit_py_plugins` `admon`/`colon_fence` in `.venv`
12. [ ] TOC scrollspy + back-to-top (SX-12)
    - Evidence: material `setting-up-navigation.md:451,498`; `site.js:13-27`
13. [ ] Mobile TOC `<details>` (SX-13)
    - Evidence: starlight `MobileTableOfContents.astro`; `site.css:540`
14. [ ] Last-updated + edit-this-page (SX-14)
    - Evidence: starlight `LastUpdated.astro`/`EditLink.astro`, `user-config.ts:200,261`

**Exit criteria:** `make quality` green for `libs/ssg` +
`libs/ssg-syntax-highlighting`; `make build-site` emits
`search-index.json` per locale, `sitemap.xml`, `robots.txt`, `404.html`;
playwright smoke covers search + theme toggle; every feature works in
both locales and degrades without JS.

## Sequence & dependencies

M8 standalone — no external blockers. NB-7 (style contract) gates NB-8…15;
NB-16 closes last. Notebook file slots `NN_` follow reader order; each item
removes the same-numbered retired parity notebook in the same commit, so
`PARITY.md` coverage dips transiently between items and is complete again at
NB-16.

M9 standalone — touches `libs/ssg`(+`-syntax-highlighting`) and `site/`
only. All SX items independent except SX-4→SX-3, SX-6→SX-5, SX-8→SX-7,
SX-14→SX-7; steps ordered quick-wins first, search slice mid-milestone,
SEO slice before the dependent freshness item.
