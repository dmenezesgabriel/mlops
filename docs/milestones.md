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
10. [ ] Close-out — README re-describe, dead helpers trimmed, full re-execute (NB-16)
    - Evidence: `projects/athena_emulator/README.md`; `projects/athena_emulator/tests/test_notebooks.py:117-143`

**Exit criteria:** `cd projects/athena_emulator && make quality` green AND
`uv run pytest projects/athena_emulator/tests -m integration` re-executes all
nine showcase notebooks against the live stack — zero FAIL rows committed in
`PARITY.md`.

## Sequence & dependencies

M8 standalone — no external blockers. NB-7 (style contract) gates NB-8…15;
NB-16 closes last. Notebook file slots `NN_` follow reader order; each item
removes the same-numbered retired parity notebook in the same commit, so
`PARITY.md` coverage dips transiently between items and is complete again at
NB-16.
