# Backlog (EPHEMERAL)

> **EPHEMERAL — iterates; never cited from code.** One work item per row,
> evidence-anchored, TDD-shaped. Group rows under a lettered section per
> workstream/domain; each section header declares its ID prefix. Prefixes
> from closed workstreams (QC/SP/PC/MD/QE/AR/CS/DP/NB/GF/QA, MQ/QH,
> AU/AF/AX) live in `docs/archive/` — reuse a prefix only for the same
> domain. Work sizes: S ≤ 1 day · M = 1–3 days · L = 3–5 days.

## A. Athena emulator showcase notebooks (NB-*)

Retitle the `projects/athena_emulator` parity probes as scenario-driven usage
showcases — one notebook per real-world consumer flow — with the evidence
machinery kept: every demonstrated feature still `record()`s a measured row
into `parity/<stem>.md` → `PARITY.md`, framed as capabilities demonstrated,
never as test probes. Prefix continues archived NB-1…6 (same domain).

| ID | Item | Work | Evidence | Depends |
|---|---|---|---|---|
| NB-7 | [x] Style contract + `01_quickstart.ipynb` (replaces `01_smoke_and_endpoints.ipynb`): persona+goal intro, ≤3-line markdown per section, canonical usage cell with real committed output, throwaway bucket/database per run + cleanup cell, closing "Capabilities demonstrated" matrix via `record()`/`persist()` — pins the pattern every later item follows | S | `projects/athena_emulator/PARITY.md` §01 (4 PASS); style ref `research_repos/aws-sdk-pandas/tutorials/006 - Amazon Athena.ipynb`; machinery `projects/athena_emulator/notebooks/_evidence.py:60-108`; hook `projects/athena_emulator/tests/test_notebooks.py:128-143` | — |
| NB-8 | [ ] `02_analytics_dataframes.ipynb` (analyst/BI reads): `read_sql_query` csv/ctas/api approaches, cache hit, chunksize iterator, categories, dtype_backend, named+qmark params, `read_sql_table`, `get_query_results` csv+manifest, list/get/wait executions, `describe_table`/`show_create_table`/column types, `create_athena_bucket`, `get_work_group`; removes `02_boto3_control_plane.ipynb` (control-plane probes re-demonstrated by NB-10/NB-11) | M | `PARITY.md` §04 (30 PASS); wrangler contracts `research_repos/aws-sdk-pandas/awswrangler/athena/_read.py:209-238`, `_utils.py:41-42,89-155`; `libs/athena-local/tests/integration/test_awswrangler_consumer.py` | NB-7 |
| NB-9 | [ ] `03_data_engineering.ipynb` (lake ETL): `wr.s3.to_parquet(dataset=True)` + partitions, `create_ctas_table`, `generate_create_query`, UNLOAD/`unload_approach`/`unload()`, `repair_table` (MSCK), `CREATE EXTERNAL TABLE`, `ALTER TABLE … ADD PARTITION`, `SHOW PARTITIONS` + `"t$partitions"`, `store_parquet_metadata`, catalog/object delete flows; removes `03_boto3_query_lifecycle.ipynb` | M | `PARITY.md` §04/§05 write+DDL rows; CTAS template `research_repos/aws-sdk-pandas/awswrangler/athena/_utils.py:860-872`; `test_awswrangler_consumer_write.py`, `test_awswrangler_consumer_partitioned.py`, `test_unload_consumer.py`, `test_alter_add_partition.py`, `test_external_table.py` | NB-7 |
| NB-10 | [ ] `04_app_integration.ipynb` (backend service): start→poll→results, get/list/batch executions, `GetQueryResults` pagination, `StopQueryExecution`, runtime statistics, prepared statements + `EXECUTE` + qmark params, named queries, `ClientRequestToken` dedupe, `ResultReuseConfiguration`, `EncryptionConfiguration` echo, catalog context; removes `04_wrangler_read_paths.ipynb` | M | `PARITY.md` §03 (21 PASS) + §02 named/prepared rows; `test_prepared_execution.py`, `test_result_reuse.py`, `test_named_queries.py`; `docs/adr/0009-async-query-execution-state-machine.md` | NB-7 |
| NB-11 | [ ] `05_governance.ipynb` (platform admin): workgroup CRUD + create-time defaults + `ConfigurationUpdates`, enforced `OutputLocation`, non-enforced fallback, managed results, disabled rejects submit, `BytesScannedCutoff`, tags tag/untag/list + ARN error taxonomy, data catalogs, `list_engine_versions`; removes `05_wrangler_write_catalog_and_gaps.ipynb` | M | `PARITY.md` §02 (15 PASS) + §03 encryption row; `test_workgroups.py`, `test_tags.py`, `test_data_catalogs.py`, `test_managed_results.py`, `test_engine_versions.py` | NB-7 |
| NB-12 | [ ] `06_iceberg_tables.ipynb` (table formats): `wr.athena.to_iceberg`, `delete_from_iceberg_table` row-delete, Glue `table_type=ICEBERG` marker mechanics | S | `PARITY.md` §05 iceberg rows; `test_iceberg_consumer.py`; `docs/adr/0013-iceberg-via-dedicated-trino-catalog-and-glue-marker-routing.md` | NB-7 |
| NB-13 | [ ] `07_aws_cli.ipynb` (ops scripting): `%%bash`/subprocess `aws athena … --endpoint-url` cells over the shipped example inventory — workgroup/named-query/data-catalog CRUD, tags, `start-query-execution` → `get-query-execution`/`get-query-results`/`stop-query-execution` | M | 28 `.rst` examples `research_repos/aws-cli/awscli/examples/athena/`; `libs/athena-local/tests/_cli_examples.py`; `test_aws_cli_consumer.py`, `test_aws_cli_query_executions.py`; `aws` binary = workspace `.venv/bin/aws` (awscli 1.46.1, `libs/athena-local/pyproject.toml:16`) | NB-7 |
| NB-14 | [ ] `08_terraform_iac.ipynb` (IaC): terraform `init → apply → plan -detailed-exitcode → destroy` over the five `aws_athena_*` resources; host binary or `docker run` via mounted socket in-container; `TF_PLUGIN_CACHE_DIR` enables offline init | M | `libs/athena-local/tests/terraform/apply/main.tf:35,52,58,66,73` (5 resources) + `versions.tf` + `.terraform.lock.hcl` + `.plugin-cache/`; `test_terraform_apply.py`; `_terraform_harness.py:96,108`; `docker-compose.yml:102` socket mount | NB-7 |
| NB-15 | [ ] `09_boundaries.ipynb` (operational limits): error taxonomy — submit-time 400s (syntax / unknown catalog / missing `OutputLocation` / disabled workgroup), runtime `FAILED` + `StateChangeReason`, pre-finish `GetQueryResults` 400, `ResourceNotFoundException` 404, out-of-scope ops shaped `InvalidRequestException` | S | `PARITY.md` §02/§03/§05 error rows; `docs/adr/0004-studio-apis-out-of-scope.md`; `test_query_error_mapping.py` | NB-7 |
| NB-16 | [ ] Close-out: `README.md` re-described as showcases; `_helpers.py`/`test_helpers.py` trimmed of whatever the showcases no longer call; full `pytest -m integration` re-execute; `PARITY.md` consolidated; milestone + PRD boxes checked | S | `projects/athena_emulator/README.md:1-9,15-24`; `tests/test_notebooks.py:117-143`; vulture/bandit scope `projects/athena_emulator/Makefile:30-32` | NB-8…15 |

## Definition of Done (all items)

- Evidence cell cites `file:line` or measured numbers — never "should".
- TDD where behavior changes: failing test first; pure refactors keep
  existing tests green.
- Gates green for the touched package (`make quality`), numbers recorded
  in the commit body.
- Item box checked in the same commit; owning milestone step updated.
