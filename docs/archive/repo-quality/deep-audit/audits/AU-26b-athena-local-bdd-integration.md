# AU-26b — athena-local bdd/integration/consumer-surface audit (2026-10-08)

Scope: `tests/{bdd,integration,terraform}/**` — bdd 11 step modules / 2,738 LOC
+ 11 features / 405 Gherkin lines / 53 scenarios / 180 step registrations;
integration 35 files (30 `test_*` + 5 harness) / 7,188 LOC / 193 collected tests
(124 fns; the botocore parity loop parametrizes ×70); terraform harness 2 Go
files / 320 LOC driven from 4 integration files (746 LOC). Split-fix
2026-10-08 (with AU-26a covering `tests/unit/**`): 9,926 test LOC was one
L-sized item. AU-20…AU-25 verified the `src/` planes; AU-26a verified the unit
suite; this audit verifies the suites that exercise the planes over
production-like seams — scenario/step quality, the 5-consumer-surface matrix
(feeds AX-2), docker-gated skip visibility, and the shared harness D-walk.

## Surface inventory

| Suite | Modules | LOC | Collected | Runtime deps |
|---|---|---|---|---|
| bdd `tests/bdd` | 11 step modules + 11 `.feature` (405 lines) | 2738 | 53 scenarios, 180 step registrations | none — in-memory stores + module-named statement-client fakes; **0 client imports** (0 httpx/boto3/botocore) |
| integration `tests/integration` | 30 `test_*` + `_consumer_harness` (226), `_cli_harness`, `_cli_examples`, `_terraform_harness`, `conftest` | 7188 | 193 (124 fns) | in-process uvicorn/moto for most; compose Trino/moto, real `aws`, `terraform`, `go` for the gated rest |
| terraform `tests/terraform` | `endpoint_routing_test.go` (26), `provider_operation_shapes_test.go` (294) | 320 | 2 via `run_go_test`; apply/parity via `run_terraform` (7 pytest fns in integration) | Go toolchain, terraform v1.16.3, registry plugins (`.plugin-cache` gitignored `.gitignore:52`) |

### Consumer-surface matrix (feeds AX-2)

| Surface | Exercised | Evidence | Hole |
|---|---|---|---|
| boto3/botocore over HTTP | **70/70** declared ops (36 implemented + shaped errors) | `test_botocore_parity_loop.py` (×70), `test_botocore_smoke.py` | — |
| AWS CLI | **28/36** implemented ops — the stems `awscli` ships examples for | `test_aws_cli_consumer.py:47-84` (`EXPECTED_EXAMPLE_STEMS`), `test_aws_cli_query_executions.py` | 8 implemented ops never CLI-exercised: the 6 PreparedStatement ops + `ListEngineVersions` + `GetQueryRuntimeStatistics` (awscli ships no example) |
| awswrangler | 39 tests / 7 files — read, write, CTAS, partition, unload, iceberg, external table | `test_awswrangler_consumer{,_partitioned,_write}.py` (4/8/6), `test_unload_consumer.py` (6), `test_iceberg_consumer.py` (5), `test_external_table.py` (3), `test_alter_add_partition.py` (7) | routed-op subset; wire parity covered by the 70-op loop |
| terraform (Go provider) | **16/36** implemented ops shaped | `tests/terraform/provider_operation_shapes_test.go` | 20 implemented ops not exercised |
| notebooks | **0** in-package (`grep -r notebook tests/` → 0) | — | covered out-of-package: `projects/athena_emulator/tests/test_notebooks.py` (16 fns) |

## Callgraph

```
uv run pytest (libs/athena-local/Makefile:15 `test`; testpaths=["tests"], addopts -q -rfEs)
├── tests/bdd/test_*.py — pytest-bdd: scenarios("*.feature") at import; generated test fns
│   ├── Given/When → src handlers + stores directly (0 client imports)
│   ├── executor paths → module fakes _TerminalStatementClient (test_managed_results.py:39),
│   │   _UnusedStatementClient (test_query_executions.py:29) — stack-independent
│   └── Then → outcome fixtures recorded by When (assert-strength measured below)
├── tests/integration/test_*.py
│   ├── conftest fixtures: LiveAthenaServer (:52, uvicorn on _pick_free_port :78),
│   │   LiveMotoServer (:32, moto server thread)
│   ├── compose gates → pytest.skip: Trino _consumer_harness.py:91, bridge moto :188
│   │   (module docstring :13-15 promises "a cold stack never fails CI … the compose
│   │    stack pins the deployed service separately" — no such pin exists in this repo's CI)
│   ├── _cli_harness.py → argv subprocess `aws` (skip :218 if absent)
│   └── _terraform_harness.py → run_go_test :43 / run_terraform (skips :40 go, :103 terraform;
│       strict ATHENA_GO_REQUIRED :38 / ATHENA_TERRAFORM_REQUIRED :101 — set nowhere outside
│       the policy test)
└── tests/unit — AU-26a scope (not audited here)
```

## Boundary table

| Boundary | Where | Faked as | Test |
|---|---|---|---|
| Trino coordinator | `_consumer_harness.py:45` (`ATHENA_LOCAL_TRINO_URL`, default `:8485`) | live compose; `pytest.skip` :91 | 64 compose-gated integration tests |
| bridge moto S3 | `_consumer_harness.py:46,171-189` | live compose `:5000`; `pytest.skip` :188 | awswrangler consumer suites |
| in-process moto/Glue | `conftest.py:32` `LiveMotoServer` | moto server thread | S3/Glue tests without compose |
| emulator HTTP | `conftest.py:52` `LiveAthenaServer` | uvicorn in-process, random port | boto3/httpx client tests |
| Trino statement client (bdd) | `test_managed_results.py:39`, `test_query_executions.py:29` | named fakes serving one finished page | bdd executor scenarios (no stack) |
| AWS CLI binary | `_cli_harness.py:218` | real awscli 1.46.1 (dev group) | 7 CLI tests |
| Go toolchain | `_terraform_harness.py:33-41` | real `go` (absent on this host → 2 skipped) | endpoint routing + provider parity |
| terraform binary | `_terraform_harness.py:81-103` | real terraform + `.plugin-cache` | harness (5) + apply (1) + parity (1) |
| subprocess execution | `_terraform_harness.py:43-80`, `_cli_harness.py` | argv lists + timeouts, `pytest.fail` on exit≠0 | D8 below |

## Dimension findings

| Dim | Suspect / measured | Evidence | Disposition |
|---|---|---|---|
| D1 | `_get_deleted_error` Then in 3 bdd files looked assert-free in the regex scan | full bodies read: `try/except … else: raise AssertionError` (`test_data_catalogs.py`, `test_named_queries.py`, `test_prepared_statements.py`) | Innocent |
| D1 | teardown deletes only the first S3 page | probe P (moto, 1001 keys): 1000 deleted, `k1000` leaked, `BucketNotEmpty` swallowed `_consumer_harness.py:147-153` | Measured → **G-298** |
| D2 | scaling claims in a test suite | no perf surfaces; harness polls deadline-bounded | Out of scope |
| D3 | gate `pyright src` = 0 but tests carry strict debt; AU-26a D3 says "pyright strict 0 on tests (gate)" | fresh runs (table below) — claim does not reproduce under any invocation | Measured → **G-299** + correction note below |
| D4 | named fakes, inline mocks | 4 named fakes in bdd (`_TerminalStatementClient` et al.); `grep MagicMock\|unittest.mock\|@patch` over bdd+integration = **0** | Clean |
| D5 | file/function size | largest bdd 453 (`test_prepared_statements.py`), largest integration 423 (`test_aws_cli_consumer.py`) — all <500; xenon B-gate green | Clean |
| D6 | unbounded growth in harness | per-test uuid buckets/DBs + `finally:` teardown sweeps | Clean by construction |
| D7 | sleeps / port races | 14 sleep sites, all deadline-bounded poll loops; `_pick_free_port` probe-then-rebind TOCTOU `conftest.py:78-81` | Polls clean; TOCTOU **suspect — report-only** (unmeasured) |
| D8 | shell injection, silent subprocess | `grep "shell=True\|eval("` = **0**; argv-list subprocess + timeouts (`GO_TEST_TIMEOUT_SECONDS`, CLI timeouts); `run_go_test` `pytest.fail`s on exit≠0 `_terraform_harness.py:76-80`; `.plugin-cache` gitignored `.gitignore:52` | Clean |
| D9 | scenario assertion strength | mutation battery over **all 11** bdd files (table below): 7 killed, 3 headline scenarios survive, 1 pin probe; zero-assert AST scan of **124** integration test fns → 2 flagged, both honest (`_assert_*` helpers; Go test + `pytest.fail`); bdd step scan of 180 registrations: 13 Given / 59 When without assert (setup/act — legitimate), Then flags 4 → 3 honest, 1 vacuous | 3 survive → **G-294/295/300**; pin → **G-296** |
| D10 | docker-gated tests invisible to gates/CI | 16 skip sites / 14 integration files (0 in bdd); cold-stack run → 127 passed/**66 skipped**, exit 0 (64 compose-gated + 2 Go = 34% of 193); warm → 244 passed/2 skipped; `ci.yml:44` runs `make test` with **no compose step** (grep all workflows: only site buildx `:99,:102`); `*_REQUIRED` flags set nowhere automated | Measured → **G-297**; surface matrix → AX-2 |

## Measurements

Baselines (compose stack live on this host unless noted):

| Run | Result |
|---|---|
| `uv run pytest tests/bdd tests/integration` (warm) | 244 passed, 2 skipped (Go toolchain), 178.84 s |
| `uv run pytest tests/bdd` ×2 | 53 passed both runs (repeatable, sub-second) |
| cold stack (`ATHENA_LOCAL_TRINO_URL=http://localhost:1 ATHENA_LOCAL_MOTO_ENDPOINT_URL=http://localhost:1 pytest tests/integration`) | 127 passed, **66 skipped, exit 0** (64 compose-gated + 2 Go) |
| `pytest tests/bdd tests/integration --cov` | 86 % line (unit: 97 % — AU-26a) |

Mutation battery — every probe reverted, `git status --short src/` empty after each:

| # | Probe (mutant) | bdd result | Killed by | Verdict |
|---|---|---|---|---|
| T | `tags.py:106` persist → `pass` | `test_tags.py` **1 failed / 4 passed** — only the workgroup roundtrip dies; `test_data_catalogs_accept_tags` **passes** (Then `test_tags.py:157-166` records `outcome.tags`, asserts nothing) | unit `test_tags.py` 7 failed; integration `test_tags.py` 3 failed | survives named scenario → **G-294** |
| C | `dispatch.py:87` `split(".")[-1]` → `[0]` | `test_canonical_model.py` **3 passed** — the Then (`:126-141`) asserts `f"{prefix}.{op}".split(".")[-1] == op` on a string it builds itself, never calling `resolve_operation` | unit `test_dispatch.py` 9 failed / 10 passed | survives whole file → **G-295** |
| A | `query_executions.py` `get_query_execution` → `return {}` | `test_artifacts.py` **5 passed** — Then (`:231-238`) asserts `outcome.record.to_payload()` from the When's `_build_record` (`:165`), never the handler the scenario names (`artifacts.feature:40`) | unit `test_query_executions.py` + `test_start_execution_reuse.py`: 7 failed / 26 passed | survives whole file → **G-300** |
| E | `engine_versions.py` pinned engine string wrong | `test_engine_versions.py` **1 failed** — Thens re-invoke the handler against feature-text literals (`test_engine_versions.py:21-42`) | — | **killed** (positive control; the When being `pass` is cosmetic) |
| M | `executor.py` `self._tasks` → `self._background_work` (3 sites :106,:228,:241, faithful rename) | `test_managed_results.py` **1 failed** — `AttributeError … '_tasks'` at step `:142` | unit suite: **74 failed / 1064** (same pin in 10 unit files) | pin → **G-296** |
| P2 | `data_catalog_state.py:93` create does not persist | `test_data_catalogs.py` **6 failed / 2 passed** | — | **killed** |
| P3 | `state.py` `NamedQueryStore.create` does not persist | `test_named_queries.py` **6 failed / 1 passed** | — | **killed** |
| P4 | `state.py` `PreparedStatementStore.create` does not persist | `test_prepared_statements.py` **7 failed / 1 passed** | — | **killed** |
| P5 | `state.py:145` `WorkGroupStore.create` does not persist | `test_workgroups.py` **4 failed / 1 passed** | — | **killed** |
| P6 | `query_results.py:53` `offset = _next_token_offset(payload)` → `offset = 0` | `test_query_executions.py` **2 failed / 1 passed** | — | **killed** |
| P7 | `catalog_metadata.py:95` `GetDatabase` returns a bare name | `test_catalog_metadata.py` **2 failed / 5 passed** | — | **killed** |
| PG | teardown pagination: 1001-key bucket (moto in-process) | first page 1000 keys `IsTruncated=True` (`_consumer_harness.py:198`, no `ContinuationToken` loop) → 1 object leaked (`k1000`), `delete_bucket` → `BucketNotEmpty`, swallowed `:147-153` | — | latent defect → **G-298** |

Pyright (package venv, pyright 1.1.391):

| Invocation | Result |
|---|---|
| `uv run pyright src` (the gate — `Makefile:13`) | **0 errors** |
| `uv run pyright tests` | **3695 errors** — bdd 364, integration 2130, unit 1165, `_parity.py` 36 |
| bare `uv run pyright` (in-package) | 3695 |
| from repo root `pyright libs/athena-local/tests` (root standard config) | 754 |

**Correction to AU-26a (D3 row, `AU-26a-athena-local-unit-suite.md:71`)**: the
verdict "pyright strict 0 on tests (gate) — Clean" does not reproduce — the
gate is `pyright src` only (`Makefile:13`) and `pyright tests` yields 3695
strict errors. Tests are outside the gate by repo convention (identical
`pyright src` in every package Makefile — the QH-2 baseline), so the substance
of the correction is: the report should say "tests excluded from the gate
(3695 unbudgeted strict errors)", not "0 on tests". AU-26a's file is not
edited (one backlog item per session); registered as **G-299**.

## Gaps promoted

| Gap ID | Severity | One-line |
|---|---|---|
| G-294 | S4 | bdd `test_data_catalogs_accept_tags` (tags.feature:22) passes under a `TagResource` that never persists — its Then records `outcome.tags` and asserts nothing (`test_tags.py:157-166`); unit + integration kill the mutant |
| G-295 | S4 | "Every operation dispatches as the final segment of X-Amz-Target" is tautological — the Then (`test_canonical_model.py:126-141`) splits a string it built itself; a `resolve_operation` mutant survives the whole file (unit dispatch kills it) |
| G-296 | S4 | bdd step awaits `executor._tasks` private attr (`test_managed_results.py:142`); faithful rename → bdd 1 failed + **74 unit tests** failed; no public wait seam exists (`ensure_query_finished` raises pre-terminal, `executor.py:271`) — G-293 class |
| G-297 | S4 | compose-gated tests invisible to every gate: cold stack → 66/193 integration tests skip with exit 0; CI (`ci.yml:44`) has no compose step; `ATHENA_*_REQUIRED` strict flags set nowhere automated |
| G-298 | S3 | teardown drops one S3 page (`_consumer_harness.py:192-204`): 1001-key bucket leaks 1 object, `BucketNotEmpty` swallowed `:147-153` — silent leak on shared compose moto; latent (no test writes >1000 keys) |
| G-299 | S3 | tests outside the type gate: `pyright tests` = 3695 strict errors while AU-26a's D3 records "0 on tests (gate)" — correct the report row and state the `pyright src` scope explicitly |
| G-300 | S4 | "GetQueryExecution reports the full artifact OutputLocation" (artifacts.feature:40) never invokes the handler — `get_query_execution → {}` mutant passes all 5 bdd tests; unit kills it |

## Suspects (report-only, unmeasured)

- `_pick_free_port` TOCTOU (`conftest.py:78-81`): probe-bind-close-then-rebind
  races a concurrent process for the port; would need a port-thief stress to
  promote (D7 measurement standard).
- CLI 8-op and terraform 20-op matrix holes (Surface inventory): structural —
  awscli ships no example for those ops; the Go parity file picks 16. Not
  defects; feed the AX-2 matrix.
- `run_go_test` cross-language assertion (`_terraform_harness.py:43-80`):
  routing asserts live in `endpoint_routing_test.go:16-26` and surface as
  `pytest.fail` — honest, but invisible to Python coverage; note only.
