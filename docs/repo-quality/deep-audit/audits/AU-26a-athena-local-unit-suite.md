# AU-26a — athena-local unit suite quality audit (2026-10-08)

Scope: `tests/unit/**` — 49 test files, 14,596 LOC, 1138 passing tests
(6.51 s wall, single run), 97% line coverage of `src/` (3932 stmts, 108
missed). Split-fix 2026-10-08 (with AU-26b covering `tests/{bdd,integration,
terraform}/**`): 24,158 test LOC was one L-sized item. Upstream reuse:
AU-20…AU-25 plane audits measured `src/` line coverage, mutation batteries,
and named-fake boundaries; this audit verifies the *suite* that produces
those numbers — AAA shape, fake quality, assertion strength, fixture
hygiene, and what a mutant flip can survive.

## Surface inventory

| Plane (verifying audit) | Test modules | Shared fakes |
|---|---|---|
| executor (AU-24) | `test_executor{,_submit,_cancel,_completion,_reuse,_unload,_iceberg}.py`, `test_start_query_execution.py`, `test_start_execution_reuse.py`, `test_start_query_context.py`, `test_query_executions.py`, `test_prepared_execution.py`, `test_statement_classification.py`, `test_get_query_results.py`, `test_result_shapes.py` | `_executor_fakes.py` (`ScriptedStatementClient`, `GatedStatementClient`, `RecordingWriter`, `FailingWriter`, `GatedWriter`, `CancellingWriter`, `RecordingSnapshotter`), `_query_execution_fakes.py` (`TerminalStatementClient`, `RecordingResultWriter`) |
| state (AU-21) | `test_state.py`, `test_executions.py`, `test_execution_store.py`, `test_execution_retention.py`, `test_prepared_statements.py`, `test_prepared_statement_lists.py` | `_execution_fakes.py` (`succeeded_execution`) |
| SQL rewrite (AU-22) | `test_dialect.py`, `test_sql_lexing.py`, `test_external_table.py`, `test_partition_alter.py` | — (pure functions) |
| iceberg (AU-23) | `test_iceberg.py`, `test_iceberg_routing.py`, `test_iceberg_probe.py` | `_iceberg_fakes.py` (`route`, `StaticIcebergProbe`) |
| boundary/artifacts (AU-25) | `test_trino_client.py`, `test_glue_proxy.py`, `test_s3_writer.py`, `test_artifacts.py`, `test_output_targets.py` | `_s3_fakes.py` (`RecordingObjectStore`, `s3_client_error`), `ScriptedTrinoHandler`/`RefusingTrinoHandler` (in `test_trino_client.py:60,77`) |
| protocol (AU-20) + handlers (AU-27) | `test_main.py`, `test_dispatch.py`, `test_errors.py`, `test_error_mapping.py`, `test_workgroups.py`, `test_schemas.py`, `test_pagination.py`, `test_request_fields.py`, `test_named_queries.py`, `test_tags.py`, `test_data_catalogs.py`, `test_catalog_metadata.py`, `test_engine_versions.py` | `_glue_fakes.py` (`FakeGlueClient`, `client_error`) |
| wire-parity / CLI / smoke | `test_botocore_parity_loop.py`, `test_cli_examples.py`, `test_smoke.py` | `tests/_parity.py` (`stub_payload`, `assert_success_body`, `assert_shaped_error`, `fast_fail_glue_proxy`) |

## Callgraph

```
pytest → test module → subject under test → (real store | named fake)

  executor tests  → BuildQueryExecutor/SubmissionPlanner/QueryExecutor
                  → ScriptedStatementClient (Trino HTTP) / RecordingWriter /
                    RecordingSnapshotter / GatedStatementClient (semaphore)
  state tests     → WorkGroupStore/NamedQueryStore/PreparedStatementStore/
                    ExecutionStore (real, in-memory) → TTL + cap arguments
  SQL/iceberg     → to_trino_dialect/unload_trino_submission/iceberg_* (pure)
  boundary tests  → S3Writer/GlueProxy/ArtifactWriter/TrinoClient
                  → RecordingObjectStore / FakeGlueClient / ScriptedTrinoHandler
  protocol/handlers → POST / via TestClient → dispatch → handler → store
  parity loop     → 70-op stubs → TestClient(app) → dispatch (all ops)
```

Every test constructs its subject through a composition-root double or a
real in-memory store; zero tests construct a boto3/trino client directly
(grep clean).

## Boundary table

| Boundary | Where | Faked as | Test |
|---|---|---|---|
| moto Glue (botocore) | `glue_proxy.py:46` Protocol | `FakeGlueClient` (`tests/unit/_glue_fakes.py`) — mirrors moto `models.py:346-417` incl. `Expression` regex | `test_glue_proxy.py`, `test_catalog_metadata.py`, `test_iceberg_routing.py` + 4 more |
| S3 object store | `s3_writer.py` `ObjectStoreClient` Protocol | `RecordingObjectStore` (`tests/unit/_s3_fakes.py`) — records put/list/delete, injectable error | `test_s3_writer.py`, `test_artifacts.py`, `test_output_targets.py` |
| Trino HTTP | `trino_client.py:60-121` | `ScriptedTrinoHandler` (`test_trino_client.py:60`) / `ScriptedStatementClient` (`_executor_fakes.py:50`) | `test_trino_client.py`, `test_executor*.py` |
| artifact writer | executor completion | `RecordingWriter`/`GatedWriter`/`CancellingWriter`/`FailingWriter` (`_executor_fakes.py:164-229`) | `test_executor_completion.py`, `test_executor_cancel.py` |
| iceberg probe | `iceberg_probe.py` TTL | `StaticIcebergProbe` (`_iceberg_fakes.py`) | `test_iceberg_probe.py`, `test_executor_iceberg.py` |
| env (`TRINO_URL_*`, `ATHENA_MOTO_ENDPOINT_URL`, `MAX_RETAINED_*`) | `main.py` composition root | `monkeypatch.setenv/delenv` | `test_main.py:394-420`, `test_main.py:161-188` |
| `uuid4` ids / clocks | `executions.py:32`, iceberg probe TTL | real / `clock=lambda:` at `test_iceberg_probe.py:89` | `test_executions.py`, `test_iceberg_probe.py` |

No subprocess, filesystem (outside tmp), network, `time.sleep`, `random`,
or `datetime.now()` anywhere in `tests/unit` (grep clean) — F.I.R.S.T.
fast/independent/repeatable holds structurally.

## Dimension findings

| Dim | Suspect / measured | Evidence | Disposition |
|---|---|---|---|
| D9 | **Redundant guard in `offset_page` survives the suite**: flip `start_index >= len(items)` → `>` (`pagination.py:39`) → all 1138 unit tests stay green; equivalence check over the token domain ([None,"0".."99"] × max_results [None,1,2,50]) finds **0 divergent cases** — for `start_index ∈ {len, len+1, …}` the guard's `([], None)` is byte-identical to the slice path's output, so the early return is dead code no test can ever pin | mutation probe M-PG below | **G-291 (S3)** — fold into G-248's `_token_offset` fix surface (same file) or delete the guard with a comment |
| D9 | **Zero-assert idempotence test**: `test_drop_table_missing_entry_is_already_clean` (`test_output_targets.py:351`) has no assert; probe shows the "already clean" drop **does** issue `delete_table(('analytics','gone'))` against Glue and swallows `EntityNotFoundException` (`output_targets.py:126-137`) — a no-op `drop_table` passes the test, and the name/docstring ("cleanup is already satisfied") misdescribe the attempt+swallow behavior | probe P-DT below | **G-292 (S4)** |
| D9 | **Wiring tests pin private names 3-4 levels deep**: `test_main.py:402-403,415-419` assert `executor._client._statement_url` and `executor._writer._s3._client.meta.endpoint_url`; a behavior-preserving rename of `TrinoClient._statement_url` fails both tests with `AttributeError` — the tests pin implementation shape, not the wiring contract | probe P-RN below | **G-293 (S4)** |
| D10 | Unit→integration import direction: `test_cli_examples.py:13` imports `tests.integration._cli_examples` (the installed-awscli example-stem helper); the unit suite depends on a module owned by the integration/CLI-parity suite, and the resources seam (`example_stems`/`load_example`) is tested only in integration | `tests/integration/_cli_examples.py:28-40`; consumers `test_aws_cli_consumer.py:28`, `test_aws_cli_query_executions.py:13` | Suspect — report only (relocate helper to `tests/_cli_examples.py` at AX-1; no failing behavior today) |
| D9/D10 | `test_main.py`'s autouse fixture resets only `workgroup_store` (`test_main.py:48-52`); the shared `execution_store`/`named_query_store`/`prepared_statement_store`/`data_catalog_store` (module globals, `main.py` composition root) survive across tests except where `reset_query_plane()` is called inline | order probe: `test_botocore_parity_loop` + `test_main` in both module orders → green both ways | Innocent today — report note only (future store-writing tests need the reset; F.I.R.S.T. independence) |
| D9 | `test_smoke.py:7` pins `__version__ == "0.1.0"` | `pyproject.toml:3` — every version bump must edit the test | Report note only — deliberate build-metadata pin |
| D3 | Types honest across the suite: `pytest.MonkeyPatch`/`TestClient`/fixture annotations everywhere, `_parity.stub_payload` returns `dict[str, object]`; pyright strict 0 on tests (gate) | reading + gate | Clean |
| D4 | Fakes centralized in 6 shared modules + `tests/_parity.py`; no inline `MagicMock`/`unittest.mock`/`patch` anywhere in `tests/unit` (grep clean); no dead fakes (each `class Fake*` has ≥2 test modules consuming it) | grep + callgraph | Clean |
| D5 | Test files 7–668 LOC, one subject per file, AAA-commented where needed; `_executor_fakes.py` name-collision-free | reading | Clean |
| D6/D7 | Stores/records mutated only through the subject; module-scoped `TestClient` in the parity loop guarded by an autouse full-store reset (`test_botocore_parity_loop.py:60-71`, ADR-0003); executor stress patterns (gather, gated writers) reused by AF-118/AF-119 tests | reading | Clean |
| D8 | No user-facing injection surface in unit tests beyond env vars (scheme-gated, `test_main.py:394-420`) | reading | Clean |

## Measurements

**Suite run**: `pytest tests/unit` → **1138 passed in 6.51 s** (pre-commit
config: `-q -rfEs --tb=short --import-mode=importlib`). Coverage:
`--cov=src` → **97%** (3932 stmts, 108 missed); the missed set is the union
of the guard/error arms documented by G-250/G-255/G-260/G-263/G-267/G-276/
G-287 (registered by AU-20…AU-25), i.e. none of the AU-26a findings below
sits on an uncovered line.

**Mutation battery** (fail-then-revert, 10 probes, targeted suites):

| # | Flip | Result |
|---|---|---|
| M-PG | `pagination.py:39` `start_index >= len(items)` → `>` | **SURVIVED** — equivalent by construction (0 divergent cases over the tested domain, above) |
| M-P1 | `pagination.py:42` `max_results > 0` → `>= 0` | KILLED |
| M-R1 | `result_shapes.py:73` `len(columns) != 1` → `!= 0` | KILLED |
| M-R2 | `result_shapes.py:58` `== "partition key"` → `!= "partition key"` | KILLED |
| M-DT | `output_targets.py:137` `except MetadataException:` → `except Exception:` | KILLED (errors test) |
| M-E1 | `errors.py` `InternalServerException` → `InvalidRequestException` | KILLED (note: my harness's in-place edit left a stale `__pycache__` after the `git checkout` revert — purged before the final runs; harness artifact, not a suite finding) |
| M-ST | `state.py:52` `if state not in WORKGROUP_STATES:` → `in` | KILLED |
| M-RF | `request_fields.py:81` bool-exclusion dropped | KILLED |
| M-WU | `workgroup_updates.py:85` unknown-member preserved filter no-op'd | KILLED |

**P-DT — drop-table probe**: adding `assert client.delete_table_calls == []`
to `test_drop_table_missing_entry_is_already_clean` fails
(`[('analytics', 'gone')] == []`) — the missing-entry drop reaches the wire
and swallows, the test asserts nothing about it.

**P-RN — private-rename probe**: rename `TrinoClient._statement_url` →
`_statement_endpoint` (behavior preserved) → both
`test_build_query_executor_*` wiring tests fail at `test_main.py:402,415`
with `AttributeError`. Reverted.

**Order probe**: `test_botocore_parity_loop` + `test_main` (the two modules
exercising module-global composition-root state), run in both orders →
green both ways.

## Gaps promoted

| Gap ID | Severity | One-line |
|---|---|---|
| G-291 | S3 | `pagination.py:39` `offset_page` early-return guard is dead code — `>=`→`>` mutant survives the full unit suite; provably equivalent to the slice path (0 divergent cases); overlap G-248's `_token_offset` fix (same file) |
| G-292 | S4 | `test_output_targets.py:351` zero-assert idempotence test — the "already clean" drop issues `delete_table(('analytics','gone'))` + swallows not-found; a no-op `drop_table` passes; name/docstring mismatch attempt+swallow vs skip |
| G-293 | S4 | `test_main.py:402-403,415-419` wiring tests pin private attrs 3-4 levels deep (`executor._client._statement_url`, `executor._writer._s3._client.meta.endpoint_url`) — behavior-preserving rename fails the suite with `AttributeError` |