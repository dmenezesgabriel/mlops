# Deep-audit backlog (EPHEMERAL)

> **EPHEMERAL WORK ITEMS — iterate freely; never cited from code.** One row
> per item; check the box when the item's acceptance is met. `AU-*` items are
> read-only audits producing `audits/AU-NN-*.md` + `gaps.md` rows; `AF-*`
> items are promoted fixes; `AX-*` are cross-cutting sweeps. Sizes:
> XS <150 LOC · S <500 · M <1500 · L ≥1500 (pre-split where shown).

## A. Bootstrap

- [x] **AU-00 — documentation set**: README (inventory, seeds), methodology,
  prd, prompt-execution, backlog, milestones, gaps, ADR-0001…0005.
  Evidence: `docs/repo-quality/deep-audit/`. Acceptance: doc map complete;
  session landed this commit. Size: XS.

## B. Package audits (dependency order — README inventory)

| ID | Item | Evidence (measured anchors) | Acceptance | Size |
|---|---|---|---|---|
| AU-01 | [x] done 2026-09-28 — report `audits/AU-01-mlops-shared.md`; 10 gaps promoted (S1×1, S3×8, S4×1); spike verdict: no re-split | **Spike**: audit `libs/mlops-shared` — calibrates rubric + effort sizing for all later items | 276 src LOC; `config.py`, `logging.py`, `pipeline.py`, `datasets.py`, `evaluation.py`, `paths.py`; shared by every project | Report filed; gaps promoted; effort-vs-size note in report tail drives re-splits of oversized items | S |
| AU-02 | Audit `libs/data-science-scaffold` — project generator; template correctness rides on AU-17/AU-18 consuming it | 152 src LOC; `register.py`, `scaffold.py`; `template/` generates the `projects/*` shape | Report + gaps | XS |
| AU-03 | Audit `docker/moto/glue_overlay.py` — request parsing, error shaping, dispatch safety | 357 src LOC; single-file HTTP overlay on moto Glue | Report + gaps; D8 (request parsing) mandatory | S |
| AU-04 | Audit `libs/ssg` domain + application: entities, use cases, `static_site_builder` (357), `site_preview` | ~670 src LOC; `domain/entities/{site,content_collection}.py`, `application/` | Report + gaps | M |
| AU-05 | Audit `libs/ssg` infrastructure + CLI: `markdown_content_renderer` (253), `site_config_repository` (229), `cli` (181), reloaders, `local_preview_server` | ~1470 src LOC; `infrastructure/*`, `cli.py`; entry-point loading for `ssg.*` plugin groups lives here — the contract plugins implement | Report + gaps | L |
| AU-06 | Audit `libs/ssg-syntax-highlighting` — pygments HTML post-processor | 229 src LOC; entry point `ssg.html_post_processors` → `plugin.py` | Report + gaps | S |
| AU-07 | Audit `libs/ssg-latex` — math post-processor (+ node asset handling) | 282 src LOC; entry point `ssg.html_post_processors` | Report + gaps | S |
| AU-08 | Audit `libs/ssg-notebook-render` — notebook→content renderer | 485 src LOC; entry point `ssg.renderers` → `notebook_content_renderer.py` | Report + gaps | S |
| AU-09 | Audit `libs/ssg-i18n` — `document_translator` (439), `i18n_site_variant_provider` (280), `terminology_mapper` (123), catalogs | 1135 src LOC; entry points `ssg.site_variant_providers` + `ssg_i18n.text_translators` | Report + gaps | M |
| AU-10 | Audit `libs/ssg-i18n-machine-translation` — transformers translator (model-load memory! D6 mandatory), in-memory translator, eval CLI | 603 src LOC; entry point `ssg_i18n.text_translators` | Report + gaps | M |
| AU-11 | Audit `libs/diagrams` — graphviz generation + `diagrams-cli` | 408 src LOC; subprocess/dot invocation surface for D8 | Report + gaps | S |
| AU-12 | Audit `libs/videos` domain + application: validation rules (174), `render_pipeline` (145), `director` (87), `quality_gate` (74), steps, factories | ~1400 src LOC | Report + gaps | M |
| AU-13 | Audit `libs/videos` infrastructure + CLI: `manim/renderer` (232, subprocess + temp files — D6/D7/D8 mandatory), `components` (164), `scene_builder` (106), `cli` (103) | ~1600 src LOC | Report + gaps | L |
| AU-14 | Audit `libs/videos-linter` — lint rules over video specs | 457 src LOC; depends on `videos` (reuse AU-12 contract verdicts) | Report + gaps | S |
| AU-15 | Audit `libs/sagemaker-local` — `patches.py` (317, SDK monkey-patching — signature-drift D1 mandatory), `session.py` (140), `config.py` (123) | 619 src LOC | Report + gaps | M |
| AU-16 | Audit `projects/sagemaker_*` batch — audit `sagemaker_scikit_learn` canonical `train.py` (82), then diff-sweep catboost/lightgbm/xgboost for shared defects | 4×~75 src LOC; identical pipeline shape | One report + per-project gap rows | S |
| AU-17 | Audit `projects/ml_specialization` — `configuration.py` (245 typed-config parsing), api/cli/batch_predict; **zero test LOC** — D9/D10 start here | 731 src LOC, 0 test LOC | Report + gaps; S4 rows expected | M |
| AU-18 | Audit `projects/nyc_taxi_demand_forecasting` — callstacks/types/perf (coverage already 100%: QH-5); pipeline `run()`s, feast/mlflow seams, config errors | 1615 src LOC; fakes + 70 tests exist | Report + gaps | M |
| AU-19 | Audit `projects/athena_emulator` parity glue — `test_notebooks.py`, `_evidence.py`, notebook health | 87 src LOC; notebook execution harness | Report + gaps | XS |
| AU-20 | Audit `athena-local` protocol plane — `main.py` (219), `dispatch.py` (188), `errors.py` (78), `error_mapping.py` (37), `workgroups.py` (107), `workgroup_schemas.py` (406), `common_schemas.py` (366) | ~1400 src LOC | Report + gaps | L |
| AU-21 | Audit `athena-local` state plane — `state.py` (466, in-memory stores: D6 retention + D7 races mandatory), `executions.py` (294), `execution_record.py` (333), `prepared_statements.py` (153), `data_catalog_state.py` (151) | ~1400 src LOC | Report + gaps | L |
| AU-22 | Audit `athena-local` SQL plane — `dialect.py` (387), `sql_lexing.py` (196), `hive_types.py` (206), `external_table.py` (493, DDL rewrite correctness D1) | ~1280 src LOC | Report + gaps | L |
| AU-23 | Audit `athena-local` iceberg plane — `iceberg.py` (457, reference routing), `iceberg_table.py` (393), `iceberg_probe.py` (93) | ~950 src LOC | Report + gaps | M |
| AU-24 | Audit `athena-local` execution plane — `submission.py` (458), `executor.py` (358), `query_executions.py` (378), `prepared_execution.py` (366) | ~1560 src LOC; async state machine — D7 mandatory | Report + gaps | L |
| AU-25 | Audit `athena-local` boundary+artifact plane — `trino_client.py` (274), `glue_proxy.py` (374), `s3_writer.py` (190), `artifacts.py` (224), `output_targets.py` (277), `query_results.py` (192), `result_shapes.py` (75) | ~1600 src LOC; external I/O — D8 mandatory | Report + gaps | L |
| AU-26 | Audit `athena-local` test suite quality — 24158 test LOC: AAA shape, named-fake quality, bdd scenario depth vs the 5 consumer surfaces, mutation spot-checks | `libs/athena-local/tests/**` | Report + gaps; feeds AX-2 | L |

## C. Cross-cutting sweeps (after triggering audits)

| ID | Item | Trigger | Acceptance | Size |
|---|---|---|---|---|
| AX-1 | Cross-cutting pattern sweep: every pattern flagged ≥2× in audit reports (e.g. stringized casts, ClassVar mutable state, silent `except`) gets a repo-wide grep verification + consolidated gap rows | MA-7 done | Sweep table in `audits/AX-1.md`; rows promoted | M |
| AX-2 | Integration/bdd coverage sweep: map every user-facing surface (CLIs, services, pipeline runs) to bdd scenarios; missing surfaces → S4 rows | All audits done | Surface→scenario matrix; rows promoted | M |
| AX-3 | Close-out: register empty or residual-only with written waivers; README "Known risk seeds" resolved; this doc set's status → complete in parent README | All AF-* done | Register dispositioned; docs updated | S |

## D. Fix items (promoted from `gaps.md` triage)

| ID | Item | Gap row | Severity | Acceptance | Size |
|---|---|---|---|---|---|
| AF-01 | [x] done 2026-09-28 — `_r2` hoists rss and returns 1.0 on perfect constant-actual fit; r2 now asserted on constant + non-constant paths | Fix G-01 — `_r2` returns 0.0 on constant `actual` regardless of fit; adopt sklearn `force_finite` convention (tss==0 → 1.0 when rss==0, else 0.0) + regression test | G-01 | S1 | RED→GREEN + gates | XS |
| AF-02 | [x] done 2026-09-28 — `_RESERVED_PAYLOAD_KEYS` excludes payload fields from extras; `_json_safe` str()-fallbacks non-scalars; 15 tests, 94.27% cov | Fix G-02, G-03 — `JsonLogFormatter._extra_context`: exclude reserved payload keys (`timestamp`, `level`, `logger`, `message`, `exception`) from extras; `str()` fallback for non-scalar values | G-02, G-03 | S3 | RED→GREEN + gates | XS |
| AF-03 | Fix G-04, G-05 — `RepositoryPathResolver.resolve`: relative branch resolve-then-`is_relative_to` → ValueError on escape (safe_join convention); absolute branch `.resolve()` normalized, documented opt-out | G-04, G-05 | S3 | RED→GREEN + gates | XS |
| AF-04 | Fix G-06 — `YamlMappingLoader.load`: raise ValueError naming the offending non-str key + config path instead of `str()` coercion | G-06 | S3 | RED→GREEN + gates | XS |
| AF-05 | Fix G-08, G-09 — delete `datasets.py`, `PipelineStep` + `SpyPipelineStep` test, unused `pipeline.py` imports, pyproject `[tool.vulture]` `ignore_names`+comment (keep `min_confidence`/`sort_by_size`); moots G-07 | G-08, G-09 | S3 | Gates green post-deletion | XS |
| AF-06 | Fix G-10 — residual coverage after AF-02…AF-05: `require_within` RMSE branch + exact-boundary equality (kills `>`→`>=` mutant), `configure()` body, `exc_info` branch, `root_path`; re-run uncovered-lines audit first | G-10 | S4 | RED→GREEN + gates | XS |
