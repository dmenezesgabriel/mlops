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
