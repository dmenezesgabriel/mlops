# Athena Local Emulator — documentation index

Build an AWS Athena emulator backed by **Apache Trino**, co-located with **moto**
(S3/Glue/STS), fully compatible with boto3, awswrangler (aws-sdk-pandas), the
AWS CLI, and terraform (hashicorp/terraform-provider-aws). Implemented as
`libs/athena-local`: a typed Python library plus docker images, wired into the
existing `docker-compose.yml`.

## Documentation map

| Path | Kind | Status |
|---|---|---|
| [architecture.md](architecture.md) | **Permanent** — arc42 architecture, building blocks, runtime, deployment, cross-cutting concepts, quality, risks, glossary | Keep in sync with the code |
| [adr/](adr/) | **Permanent** — architecture decision records (Nygard-style, numbered, append-only) | Supersede only with a new ADR |
| [prd.md](prd.md) | **Ephemeral** — product requirements (what/why, acceptance criteria) | Must NOT be cited from code |
| [prompt-execution.md](../../prompt-execution.md) | **Operational** — session execution protocol, mapped to this repo's files | Keep in sync with doc map |
| [backlog.md](backlog.md) | **Ephemeral** — evidence-anchored work items, TDD-shaped | Must NOT be cited from code |
| [milestones.md](milestones.md) | **Ephemeral** — ordered phases and steps with dense evidence refs | Must NOT be cited from code |

Rule enforced repo-wide: **PRD, backlog, and milestones are ephemeral working
documents; never quote their IDs or content in code, docstrings, or comments.**
Code comments may reference only permanent artifacts (`architecture.md`,
`adr/000N-*.md`) and shall cite *evidence* (file:line in `research_repos/…`),
never the working document that produced the requirement.

## Conventions used in these documents

- **Evidence citations** are repo-relative paths with `:line` anchors into the
  frozen research checkouts under `research_repos/`, plus official upstream
  docs/examples where the checkout lacks them.
- **Canonical service contract**: the AWS CLI vendors the Athena model at
  `research_repos/aws-cli/awscli/botocore/data/athena/2017-05-18/service-2.json`.
  It is byte-identical (verified: identical shapes checksum, same 70
  operations, same exceptions/enums) to the botocore 1.42.97 model installed in
  `.venv` at `.venv/lib/python3.11/site-packages/botocore/data/athena/2017-05-18/service-2.json.gz`.
  `service-2.json` is the single source of truth for the wire protocol.
  `research_repos/boto3` does **not** vendor botocore models.
- **Standards**: architecture per arc42 (https://arc42.org/documentation/);
  ADRs per the "Architecture Decision Records" community format (Status ·
  Context · Decision · Consequences); backlog/milestones are conventional but
  every step derives from evidence, never invention.
- **Process rule**: every source-code change is TDD (red → green → refactor).
  Quality gates run at every commit: pytest, pytest-cov, pytest-bdd, pyright,
  ruff, bandit, vulture, xenon, radon, semgrep, import-linter, deptry — wired
  as pre-commit hooks and per-lib `make quality`, per the repo's existing
  pattern (`libs/mlops-shared/Makefile`).

## Verified evidence index (most-referenced anchors)

| Topic | Anchor |
|---|---|
| Athena service model: 70 ops, JSON 1.1, `POST /`, `X-Amz-Target: AmazonAthena.<Op>` (dispatched on the segment after the final dot — moto `responses.py:462-464`) | `research_repos/aws-cli/awscli/botocore/data/athena/2017-05-18/service-2.json` (== venv botocore 1.42.97 model) |
| moto Athena is metadata-only; queries are not executed | `research_repos/moto/docs/docs/services/athena.rst:48` |
| moto Athena backend | `research_repos/moto/moto/athena/models.py:314` start, `:345` `_process_ddl`, `:415` get_query_results, `:475` `_store_query_result_in_s3`, `:140` `OutputLocation += f"{self.id}.csv"` |
| moto Athena dispatch / URLs / error statuses | `research_repos/moto/moto/athena/responses.py:26` (400 "WorkGroup already exists"), `research_repos/moto/moto/athena/urls.py:3`, `research_repos/moto/moto/core/responses.py:462-464` (X-Amz-Target split) |
| moto JSON-1.1 error serialization | `research_repos/moto/moto/core/serialize.py:492,538`, `research_repos/moto/moto/core/exceptions.py:100` |
| moto Glue ops Trino needs (database/table/partition layer) | `research_repos/moto/moto/glue/models.py:360` (get_databases), `:1240` (batch_get_partition), `research_repos/moto/moto/glue/responses.py` |
| awswrangler polling + terminal states | `research_repos/aws-sdk-pandas/awswrangler/athena/_utils.py:41-42` (`_QUERY_FINAL_STATES`, 1.0 s delay) |
| awswrangler `_start_query_execution` args | `research_repos/aws-sdk-pandas/awswrangler/athena/_utils.py:89-155` |
| awswrangler workgroup resolution (`GetWorkGroup`) | `research_repos/aws-sdk-pandas/awswrangler/athena/_utils.py:158-187` |
| awswrangler `.txt` utility-result contract | `research_repos/aws-sdk-pandas/awswrangler/athena/_utils.py:190-221` |
| awswrangler CTAS SQL template + error mapping | `research_repos/aws-sdk-pandas/awswrangler/athena/_utils.py:860-872`, `:888-898` |
| awswrangler `.csv` result contract (quoted header row as line 1 + QUOTE_ALL — ADR-0010) | `research_repos/aws-sdk-pandas/awswrangler/athena/_read.py:209-238` |
| awswrangler CTAS manifest contract | `research_repos/aws-sdk-pandas/awswrangler/athena/_read.py:62-81,135-206` (metadata path `:153`) |
| awswrangler inline `GetQueryResults` header-row semantics | `research_repos/aws-sdk-pandas/awswrangler/athena/_read.py:335-384` (`page_rows[1:]` at `:357`, `:383`) |
| awswrangler cache → `batch_get_query_execution` | `research_repos/aws-sdk-pandas/awswrangler/athena/_cache.py:36-45` |
| awswrangler prepared statements expect `ResourceNotFoundException` | `research_repos/aws-sdk-pandas/awswrangler/athena/_statements.py:26-29` |
| awswrangler endpoint override (`athena_endpoint_url`) | `research_repos/aws-sdk-pandas/awswrangler/_utils.py:255-280` (`:259-260`) |
| terraform core is only the CLI (no AWS SDK) | `research_repos/terraform/main.go`, `research_repos/terraform/internal/` |
| Trino client statement protocol | trino.io — `develop/client-protocol.html` (`POST /v1/statement`, `nextUri` poll, `X-Trino-User` required, `DELETE` cancel) |
| Trino Glue metastore properties | trino.io — `object-storage/metastores.html` (`hive.metastore=glue`, `hive.metastore.glue.endpoint-url/region/aws-access-key/aws-secret-key`) |
| Trino native S3 properties | trino.io — `object-storage/file-system-s3.html` (`fs.s3.enabled=true`, `s3.endpoint`, `s3.path-style-access=true`, static keys; legacy `hive.s3.*` removed) |
| Athena result-file naming + `GetQueryExecution` semantics | AWS docs — `athena/latest/ug/querying-finding-output-files.html` (`{QueryID}.csv/.txt/.metadata`, `{QueryID}-manifest.csv`) |
| LocalStack Athena reference (wrangler/pyathena wiring) | docs.localstack.cloud — `aws/services/athena` |

## Implementer starting point

Read in order: `architecture.md` → the ADR(s) your task touches → their
evidence anchors → execute your backlog item red-green. Keep PRD / backlog /
milestones out of the code; update only the permanent docs when the
architecture moves.