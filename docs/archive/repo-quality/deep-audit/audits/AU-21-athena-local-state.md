# AU-21 — athena-local state plane audit (2026-10-07)

Scope: `state.py` (466), `executions.py` (294), `execution_record.py` (333),
`prepared_statements.py` (153), `data_catalog_state.py` (151) — 1397 LOC
measured (`radon raw`; 979 SLOC). Upstream reuse: AU-20's protocol-plane
verdicts cover every shared helper the plane calls — `dispatch`
(single-threaded-by-construction argument, error funnel), `request_fields`
validators, `pagination.offset_page` (G-248 surface), `errors` shapes,
`common_schemas` parsers; AU-27's handler-family verdicts cover the wiring
pattern (D4) and the G-249/G-251/G-252 defect classes — that audit
explicitly deferred the store contracts to this one. Permanent contracts:
`docs/athena-emulator/adr/0003` (in-memory control plane), `0007` (result
artifacts), `0009` (async execution state machine), `0011` (managed
results). Parity references: vendored
`research_repos/aws-cli/.../athena/2017-05-18/service-2.json` (shapes quoted
below), moto `athena/models.py` + `responses.py`, CLI `examples/athena/*.rst`.

## Surface inventory

| Module | Public symbols | Entry points |
|---|---|---|
| `state.py` | `PRIMARY_WORKGROUP_NAME`, `WORKGROUP_STATES`, `missing_workgroup_error`, `disabled_workgroup_error`, `validated_state`, `WorkGroupRecord`, `WorkGroupStore`, `ensure_workgroup_enabled`, `NamedQueryRecord`, `NamedQueryStore`, `PreparedStatementRecord`, `PreparedStatementStore` | stores consumed via handlers + executor |
| `executions.py` | `__all__` (13 re-exports), `DEFAULT_MAX_RETAINED_EXECUTIONS`, `ExecutionStore` | executor-side (submission/executor/query_executions/query_results) |
| `execution_record.py` | `QUEUED`/`RUNNING`/`SUCCEEDED`/`FAILED`/`CANCELLED`, `TERMINAL_STATES`, `VALID_TRANSITIONS`, `QUERY_HISTORY_TTL_SECONDS`, `QueryExecutionRecord` | record type owned by `ExecutionStore` |
| `prepared_statements.py` | `create_prepared_statement`, `get_prepared_statement`, `list_prepared_statements`, `update_prepared_statement`, `delete_prepared_statement`, `batch_get_prepared_statement`, `register_prepared_statement_handlers` | ★6 handlers via registry |
| `data_catalog_state.py` | `AWS_DATA_CATALOG_NAME`, `GLUE_CATALOG_TYPE`, `missing_catalog_error`, `DataCatalogRecord`, `DataCatalogStore`, `ensure_executable_catalog` | store consumed via handlers + executor |

## Callgraph

```
register_prepared_statement_handlers (main.py composition) → 6 handlers
  CreatePreparedStatement → required_string×3/optional_string (request_fields)
                          → ensure_workgroup_enabled (state.py:197)
                          → PreparedStatementStore.create (state.py:369)
  GetPreparedStatement    → required_string×2 → store.get (:393) → to_payload
  ListPreparedStatements  → member/required_int + optional_string
                          → store.list (:403) → offset_page (G-248 surface)
                          → store.get per page item → to_summary_payload
  UpdatePreparedStatement → required_string×3/optional_string → store.update (:417)
  DeletePreparedStatement → required_string×2 → store.delete (:435)
  BatchGetPreparedStatement → required_string_list + required_string
                            → store.batch_get (:449)
Other planes' handlers → store contracts verified here:
  workgroups.py → WorkGroupStore.create/get/list/update/delete (:106-194)
  named_queries.py → ensure_workgroup_enabled → NamedQueryStore.* (:237-320)
  tags.py → in-place tags[:] mutation on WorkGroupRecord/DataCatalogRecord
  data_catalogs.py / catalog_metadata.py → DataCatalogStore.* (:58-133)
Executor-side callers (store methods are the contract; executor is AU-24/25):
  submission.py:214 → ExecutionStore.create (executions.py:92)
  submission.py:330 → find_by_request_token → _retained_execution
  submission.py:371 → find_reusable
  submission.py:195-203 → record.transition_to / reuse_results_from
  executor.py:178,195 → store.get; :214-284 → transition_to /
    apply_engine_statistics / cache_result_page
  query_executions.py:262,272,304 → store.get / batch_get / list_execution_ids
  query_results.py:67 → store.get
  prepared_execution.py:279 → PreparedStatementStore.get
```
Unreachable-looking code: none — vulture clean on all five files; every
helper has a live caller on the callgraph.

## Boundary table

| Boundary | Where | Faked as | Test |
|---|---|---|---|
| uuid4 execution/named-query ids | `state.py:260`, `executions.py:112` | real (unpinned format) | `test_named_queries.py`, `test_execution_store.py` |
| wall-clock `time()` (creation/last-modified/submission/completion) | `state.py:69,222,331`, `execution_record.py:75,155` | real; TTL expiry faked by back-dating `completion_time` | `test_execution_retention.py:31-36` |
| named record factory | `tests/unit/_execution_fakes.py` (`succeeded_execution`) | named fake | `test_execution_retention.py` |

No filesystem, network, subprocess, or env boundary in the plane itself
(env is read once at import — AU-20 scope); the stores are pure dicts.

## Dimension findings

| Dim | Suspect / measured | Evidence | Disposition |
|---|---|---|---|
| D1 | **`ListPreparedStatements` MaxResults unenforced** — 0, 1, 51 all accepted where the model declares `MaxPreparedStatementsCount` 1..50; `0` hits `offset_page`'s ≤0-is-no-limit branch and returns *everything* (G-251 class at the PS op layer — sibling handlers use bare `required_int`, `prepared_statements.py:63-64`) | probes P-A below; service-2.json shape | **G-256 (S3)** |
| D1 | **Prepared-statement member constraints unenforced** (G-252 class at the PS op layer): `StatementName` 300 chars and `"1abc"` (model pattern `[a-zA-Z_][a-zA-Z0-9_@:]{1,256}`, 1..256), `QueryStatement` 300k chars (model `QueryString` 1..262144), `Description` 2000 chars and `""` (model `DescriptionString` 1..1024), `WorkGroup` `"bad name!"` (model `WorkGroupName` pattern `[a-zA-Z0-9._-]{1,128}`) — all accepted | probes P-B below | **G-257 (S3)** |
| D1 | **`CreatePreparedStatement` accepts an unknown workgroup** — `ensure_workgroup_enabled` passes unknown names through (documented for the saved-statement stores) and the statement is stored scoped to a nonexistent workgroup; moto deliberately 400s `"WorkGroup does not exist"` (`research_repos/moto/moto/athena/responses.py:283-284`) — wire-visible divergence, unlike the named-query case where moto itself 500s | `state.py:197-209`, `prepared_statements.py:37`; probe P-B6 | **G-258 (S3)** |
| D1 | `BatchGetPreparedStatement` list cap — model `PreparedStatementNameList` declares **no** min/max (unlike `NamedQueryIdList` 1..50); 60 names accepted is model-legal | probe P-C; service-2.json shape `{}` | Closed — no model constraint to enforce |
| D1 | Duplicate named-query names accepted (two records, two IDs) — moto also accepts (`models.py:530-545` has no check); real-Athena behavior unverifiable from vendored material | `state.py:252-273`; probe P-D | Suspect — report only |
| D1 | `batch_get` echoes duplicate request IDs as duplicate found records (both stores); moto has no `batch_get_named_query` to compare; unverifiable | `state.py:305-320,449-466`; probe P-E | Suspect — report only |
| D1 | Get/List/Update/Delete prepared statements pass through on a **DISABLED** workgroup (only Create gates via `ensure_workgroup_enabled`); real-Athena behavior unverifiable from vendored material | `prepared_statements.py:49-104`; probes P-F1..F4 | Suspect — report only (documented pass-through) |
| D1 | `ExecutionStore.get` missing → `InvalidRequestException` — matches the model (GetQueryExecution errors: InternalServer + InvalidRequest, no ResourceNotFound); moto raises a bare `KeyError` → 500 (`models.py:398-400`) | `executions.py:206-212`; probe P-H | Closed — model-pinned |
| D2 | `find_reusable` O(n) scan per reuse-enabled submit; `list_execution_ids` O(n) build per list call — both bounded by the 10k cap | `executions.py:236-252,287-293`; timeit table below | Linear — innocent (bounded) |
| D3 | Record aliasing: `WorkGroupRecord.tags` / `DataCatalogRecord.parameters` stored by reference — mutating the caller's container mutates the record; unreachable from handlers (`parse_tags`/`optional_string_map` build fresh containers per call, `data_catalogs.py:55` copies) | `state.py:147`, `data_catalog_state.py:93`; probe P-I | Report note — latent store-level hazard only |
| D3 | No `cast`/`Any` in the five files; `Optional` fields hide no error paths (absent-member semantics are the wire contract) | grep clean | Honest |
| D4 | Store classes earn their place — injectable seams; every test suite binds its own store instance; the executor-side callers take the store by constructor | `state.py:106,237,354`, `executions.py:58`, `data_catalog_state.py:58` | Earns its place (AU-27 verdict pattern reused) |
| D5 | **`ExecutionStore.create` spans 50 lines (92-141) with a 17-parameter signature, and `SubmissionPlanner.create_record` adds a second 34-line kwarg wall** (`submission.py:206-239`) — adding one submit-time field touches 4 sites (StartRequest field → planner kwarg → store param → record field); `find_reusable` spans 39 lines (214-252) | measured spans | **G-259 (S3)** |
| D5 | `register_prepared_statement_handlers` 31 lines — 6 registrations, matches the sibling family style (AU-27 verdict); `same_request`/`to_payload` 28/33 lines are comparison/serialization shape | `prepared_statements.py:123-153` | Clean |
| D6 | **Retention verified**: 5000 creates @ cap 500 → store pinned at exactly 500, token map coherent (50 entries, 0 dangling), tracemalloc diff 961,172 bytes = the steady-state size of 500 retained records (bounded by cap × record size) — the "unbounded in-memory stores" risk seed is resolved by the shipped TTL+cap (`9ddd321`) | `executions.py:54,143-176`; measurement below | Verified — seed resolved |
| D6 | In-flight exceed-cap as documented: 15 live records retained @ cap 10 (executor still owns them) | `executions.py:66,148-149` | Documented — coherent |
| D6 | Control-plane stores grow only via client creates (no per-request accumulation — AU-20's `WorkGroupStore` verdict extends to the other three); deleted records leave **empty `by_workgroup` lists** (cosmetic residue, bounded by distinct workgroup names used) | `state.py:300-303,442-447`; probe P-G | Innocent (residue note) |
| D7 | Single-threaded by construction (AU-20 verdict reused: async route → event loop, sync handlers await-free, `dispatch.py:166-167`) + 4000-op asyncio stress over the real stores → every invariant held, 0 dangling token entries | stress below | Holds |
| D7 | Token-map/eviction coupling: first-wins `setdefault` + owner-eviction delete means a *later* same-token record live in history is not replayed — a retry runs fresh (measured: 1000 creates @ cap 200, 50 tokens → map drains to 0 with live tokened records remaining); the fresh-after-eviction choice is documented (`executions.py:178-186`) and pinned by three tests (`test_execution_retention.py:83-162`) | `executions.py:133-139,163-176` | Documented design — suspect, report only |
| D8 | No injection surface: pure dict stores, uuid4/time only, no fs/subprocess/SQL/yaml/pickle; error messages echo names but `json.dumps` escapes (AU-20 verdict reused); no path joins in the plane (artifact paths live in output_targets/s3_writer — AU-25) | reading | Clean |
| D9 | Coverage (unit+bdd, plane-scoped): 518 stmts, 1 missed — `execution_record.py:256`, the empty-prefix `return None` in `_result_output_location`; the 10 integration suites also miss it → **uncovered at every layer** | coverage runs below | **G-260 (S4)** |
| D9 | Mutation battery 6/7 killed; the survivor: `DataCatalogStore.update`'s absent-`Parameters` keep-branch is unasserted — flipping it to always-assign (wiping stored parameters to `None`) fails nothing in the full docker-free suite | `data_catalog_state.py:126-127`; battery below | **G-260 (S4)** |
| D10 | `prepared_statements.feature`: 8 scenarios — all six ops + a 3-page pagination walk + missing-statement/batch-unprocessed error paths; workgroups 5, named_queries 7, data_catalogs 8 scenarios (AU-20/AU-27 verified) | `tests/bdd/prepared_statements.feature` | Good depth |

## Measurements

**P-A — ListPreparedStatements cap probe** (handler-level, real stores;
model `MaxPreparedStatementsCount` 1..50):

| MaxResults | result |
|---|---|
| `0` | accepted — `offset_page` ≤0-is-no-limit returns *all* statements |
| `1` | accepted (legal) |
| `51` | accepted — over the model max |

**P-B — member-constraint probes** (all → created, `{}` output):
`StatementName` 300 chars; `StatementName="1abc"` (model pattern requires
`[a-zA-Z_]` first); `QueryStatement` 300,000 chars (model 262144);
`Description` 2000 chars (model ≤1024); `Description=""` (model min 1);
`WorkGroup="bad name!"` (model pattern `[a-zA-Z0-9._-]{1,128}`) — and the
unknown-name case stores the statement where moto 400s
(`responses.py:283-284`).

**P-C — BatchGetPreparedStatement list cap**: 60 names → accepted, 60
unprocessed entries returned. Model `PreparedStatementNameList` carries no
min/max — no constraint to enforce (dead suspect).

**P-D — duplicate named-query names**: two `CreateNamedQuery` calls named
`dup` in `primary` → two records, two different `NamedQueryId`s. moto
`models.py:530-545` also accepts (no check).

**P-E — batch_get duplicate IDs**: `NamedQueryStore.batch_get([id, id])` →
2 found records (duplicates echoed).

**P-F — disabled-workgroup pass-through**: with `primary` DISABLED,
Get/List/Update/Delete prepared statements all succeed (only
CreatePreparedStatement gates).

**P-G — delete residue**: `NamedQueryStore.delete` leaves
`by_workgroup={'wg': []}` — empty-list residue.

**P-H — missing execution error class**: `ExecutionStore.get` on a absent
id → `InvalidRequestException` — matches the model's GetQueryExecution
error list (no `ResourceNotFoundException` declared).

**P-I — parameters aliasing**: caller-mutated dict visible through the
record (`{'k': 'MUTATED'}`); unreachable from the wire path
(`data_catalogs.py:55` copies).

**D2 — scaling** (min-of-7 × 3 iterations, n = 10²/10³/10⁴):

| n | `find_reusable` | `list_execution_ids` |
|---|---|---|
| 100 | 0.129 ms | 0.039 ms |
| 1000 | 3.227 ms | 0.349 ms |
| 10000 | 16.110 ms | 4.482 ms |

Linear within the 10k cap (the 10³ `find_reusable` point is GC-noisy across
runs: 1.25–3.23 ms); no superlinear growth. Worst case ≈ 16 ms per
reuse-enabled submit at a full cap.

**D6 — retention** (`max_retained_executions=500`, 5000 terminal creates,
100 distinct `ClientRequestToken`s cycling): store pinned at exactly 500
records; `by_request_token` coherent at 50 entries (0 dangling);
`tracemalloc` diff 961,172 bytes after `gc.collect()` — the steady-state
size of the retained records, bounded by cap × record size. In-flight
exemption: 15 live records retained @ cap 10.

**D7 — stress**: 4000 interleaved ops via `asyncio.gather` (1000 ×
workgroup create/update/list/delete, 1000 × named-query
create/list/batch_get/delete, 1000 × prepared-statement
create/list/update/delete, 1000 × execution
create/transition/list/token-lookup) over the real stores → final state:
workgroups exactly `{primary, wg0}` (every i%40≠0 create deleted), 1
prepared statement (ps0), executions exactly 200 @ cap 200, 0 dangling
token entries, no corruption.

**Token-map drain probe** (the D7 report-only suspect): 1000 creates @ cap
200 with 50 cycling tokens → `by_request_token` drains to 0 while live
tokened records remain — first-wins entries are deleted when their owner
evicts, and later same-token creates never re-own the entry (it existed at
their create time). Retry then runs fresh: the documented
retention-bounded idempotency (`executions.py:178-186`), pinned by
`test_execution_retention.py:83-162`.

**Coverage** (full unit + bdd suites, plane-scoped): 518 stmts, 1 missed —
`execution_record.py:256` (empty-prefix `return None` in
`_result_output_location`; no test creates a record whose
`ResultConfiguration.output_location` is empty). Integration run (10
state-plane-relevant suites, real HTTP + moto: prepared-statements,
workgroups, named-queries, result-reuse, output-location, managed-results,
get-query-results, data-catalogs, composition-root, aws-cli
query-executions) misses `execution_record.py:256` too — union across all
layers leaves exactly that one line uncovered. 99.8% plane coverage.

**Mutation battery** (fail-then-revert; targeted suite first, survivors
re-run against the full docker-free suite):

| Mutant | Flip | Result |
|---|---|---|
| M-1 | workgroup duplicate-check inverted | KILLED (`test_workgroups.py`) |
| M-2 | PS delete drops `by_workgroup` maintenance | KILLED (full suite; the narrow `test_prepared_statement_lists.py` alone passed — noted) |
| M-3b | eviction terminal-gate removed (evicts in-flight) | KILLED (full suite) |
| M-4b | terminal-state immutability dropped | KILLED (full suite) |
| M-5 | `batch_get` found/unprocessed swapped | KILLED (`test_named_queries.py`) |
| M-6 | `DataCatalogStore.update` absent-`Parameters` keep-branch → always-assign | **SURVIVED** (full suite) |
| M-7 | `ListPreparedStatements` NextToken emission dropped | KILLED (bdd) |

M-3/M-4 first attempts were equivalent mutants (`excess <= 0`→`<` is
behavior-identical at excess=0; `VALID_TRANSITIONS.get(..., {new_state})`
differs only for impossible invalid current states) — replaced with M-3b/
M-4b. M-6 is the G-260 survivor: the keep-branch is executed (100% line
coverage) but never asserted.

**Report notes (no row)**: `WorkGroupStore.update` has no
primary-state guard (disabling `primary` is accepted — AWS allows it, no
vendored contradiction); `apply_engine_statistics`'s `isinstance(int)`
accepts `bool` (Trino stats are ints; unreachable in practice);
`validated_state` error message embeds the tuple (stable); the
`ensure_workgroup_enabled` unknown-name pass-through is the documented
design shared with named queries (AU-27 suspect reused); `offset_page`
list-copy per call is O(n) but bounded (D2 verdict reused).

## Gaps promoted

| Gap ID | Severity | One-line |
|---|---|---|
| G-256 | S3 | `ListPreparedStatements` MaxResults unenforced — 0/1/51 accepted where the model declares `MaxPreparedStatementsCount` 1..50; 0 returns everything |
| G-257 | S3 | Prepared-statement member constraints unenforced (StatementName pattern/256, QueryStatement 262144, Description 1..1024, WorkGroup pattern) — G-252 class at the PS op layer |
| G-258 | S3 | `CreatePreparedStatement` accepts an unknown workgroup — moto deliberately 400s "WorkGroup does not exist" (`responses.py:283-284`); wire-visible divergence |
| G-259 | S3 | `ExecutionStore.create` 50-line 17-param signature wall + `SubmissionPlanner.create_record` second 34-line wall — 4-site field-add path; `find_reusable` 39 lines |
| G-260 | S4 | Test-depth bundle: `execution_record.py:256` empty-prefix branch uncovered at every layer; `DataCatalogStore.update` absent-`Parameters` keep-branch unasserted (M-6 mutant survives the full suite) |
