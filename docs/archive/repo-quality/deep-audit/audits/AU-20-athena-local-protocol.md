# AU-20 — athena-local protocol plane audit (2026-10-07)

Scope: `main.py` (219), `dispatch.py` (188), `errors.py` (78), `error_mapping.py`
(37), `workgroups.py` (107), `workgroup_schemas.py` (406), `common_schemas.py`
(366), plus the direct leaf helpers the callgraph traverses — `request_fields.py`
(169), `schemas.py` (69), `workgroup_updates.py` (135), `pagination.py` (56).
1830 LOC measured (`radon raw`). Split-fix: the four helpers were unassigned in
the plane split; the seven remaining orphans were reassigned (AU-22
`partition_alter.py`, AU-24 `statement_classification.py`, new AU-27 handler
family). Upstream: no workspace audits to reuse (athena-local is last in
dependency order). Permanent contracts: `docs/athena-emulator/adr/0008`
(JSON-1.1 dispatch/error parity), `0009` (async execution), `0003` (in-memory
control plane).

## Surface inventory

| Module | Public symbols | Entry points |
|---|---|---|
| `main.py` | `build_execution_store`, `build_query_executor`, `reset_query_plane` | ★`app` (FastAPI), ★`athena_endpoint` (POST /), ★`health` (GET /health) |
| `dispatch.py` | `operation_names`, `register_handler`, `implemented_operations`, `resolve_operation`, `parse_body`, `serialize_success`, `WireResponse` | ★`dispatch` |
| `errors.py` | `AthenaError` + 5 shape subclasses, `serialize_error`, `JSON_11_CONTENT_TYPE` | — |
| `error_mapping.py` | `is_syntax_error`, `syntax_error_invalid_request` | — (consumed by executor, AU-24) |
| `workgroups.py` | `create_work_group`, `get_work_group`, `list_work_groups`, `update_work_group`, `delete_work_group`, `register_workgroup_handlers` | handlers via registry |
| `workgroup_schemas.py` | `WorkGroupConfiguration`, `to_payload`, `apply_defaults` | — |
| `common_schemas.py` | `Tag`, `EngineVersion`, `EncryptionConfiguration`, `AclConfiguration`, `ResultConfiguration`, `ResultReuseByAgeConfiguration`, `ResultConfigurationUpdates`, `ManagedQueryResults*`, parse/payload helpers | — |
| `request_fields.py` | `member`, `as_object`, `required_*`/`optional_*` validator family | — |
| `schemas.py` | re-export shim (`__all__`, 30 names) | — |
| `workgroup_updates.py` | `WorkGroupConfigurationUpdates` | — |
| `pagination.py` | `offset_page` | — |

## Callgraph

```
POST / (main.athena_endpoint:182)
  → content-length pre-check (:184-190) / body read (:191-193)
  → dispatch (dispatch.py:144)
      → resolve_operation → operation_names (botocore ServiceModel, lru_cache)
      → parse_body (json.loads; non-object → InvalidRequestException)
      → OPERATION_HANDLERS[op] — workgroup family:
          create_work_group → required_string/optional_string/member (request_fields)
                            → WorkGroupConfiguration.from_dict (workgroup_schemas
                              → common_schemas parsers → request_fields)
                            → parse_tags (common_schemas)
                            → WorkGroupStore.create (state.py — AU-21 contract)
          get_work_group → store.get → WorkGroupRecord.to_payload → to_payload
          list_work_groups → optional_max_results → store.list → offset_page
          update_work_group → WorkGroupConfigurationUpdates.from_dict
                            (workgroup_updates → common_schemas) → store.update
                            → WorkGroupConfiguration.apply_updates
          delete_work_group → store.delete
      → serialize_success / AthenaError → (main) serialize_error
GET /health (main.health:165) — outside the wire protocol
import-time composition (main.py:133-161): stores + handler registration +
  build_execution_store/build_query_executor (env parsing; executor boundaries
  are AU-24/AU-25 scope)
reset_query_plane (main.py:205) — test seam: execution_store.reset + rebind
```
Unreachable-looking code: none — vulture clean on all 11 files; every error
shape has a live emitter or is pinned protocol vocabulary (below).

## Boundary table

| Boundary | Where | Faked as | Test |
|---|---|---|---|
| botocore Athena service model (op names) | `dispatch.py:57-70` | real model; byte-parity vs vendored reference proven | `tests/bdd/test_canonical_model.py`, `test_dispatch.py:38` |
| HTTP wire (FastAPI/Starlette) | `main.py:181-202` | real `TestClient` | `test_main.py` (29 tests) |
| uuid4 requestid / wall-clock `CreationTime` | `errors.py:76`, `state.py` | real (unpinned format, length-36 asserted) | `test_errors.py` |
| Trino/moto/S3 (executor, writer, snapshotter) | `main.py:96-130` composition only | named fakes (`tests/unit/_executor_fakes.py` etc.) | AU-24/AU-25 scope |

No filesystem, subprocess, env-at-request-time, or RNG boundary in the plane
itself; env is read once at import (`main.py:66-79`, `:109-114`).

## Dimension findings

| Dim | Suspect / measured | Evidence | Disposition |
|---|---|---|---|
| D1 | **NextToken accepts any `int()`-parseable string** — negative (`-1`, `-5`), whitespace-padded (` 1 `), `+`-prefixed; `-5` emits a *negative* next-token (`-3`) and pages come back empty/scrambled where real Athena rejects an invalid token with 400; docstring claims "rejects anything it cannot decode" | `pagination.py:48-56`; probe table below | **G-248 (S3)** |
| D1 | **Canonical member constraints unenforced on the raw-wire path** — `WorkGroupName` pattern `[a-zA-Z0-9._-]{1,128}` (200-char and `../escape` accepted), `BytesScannedCutoffValue` min 10⁷ (5 accepted), `TagKey` 1..128 / `TagValue` ≤256 (200/300 accepted), `RoleArn` pattern (`not-an-arn` accepted), `WorkGroupDescriptionString` ≤1024 (2000 accepted), `NameString` min 1 (`AdditionalConfiguration: ""` accepted). botocore enforces these client-side, so the parity suites cannot see the gap; raw HTTP gets 200 where real Athena 400s (G-21/G-22 class, AU-03) | `request_fields.py:41-96`, `common_schemas.py:54-74`; vendored `service-2.json` shapes quoted below | **G-249 (S3)** |
| D1 | `_merge_managed_updates` defaults `enabled=False` when only `EncryptionConfiguration` is supplied on a never-configured workgroup | `workgroup_schemas.py:111-130` | Closed — model marks `Enabled` a `BoxedBoolean` (optional); merge keeps current when present (probe P2b); state coherent |
| D1 | `required_string` rejects whitespace-only but returns the unstripped value (`" x "` accepted) | `request_fields.py:41-47` | Folded into G-249 (pattern enforcement subsumes) |
| D2 | `from_dict`/`to_payload`/`apply_updates` over large preserved maps | probe: 0.05→0.18→1.29 ms (n=10²/10³/10⁴), slope ≈ 1 | Linear — innocent |
| D3 | botocore `cast` + scoped `pyright: ignore` at the designated boundary | `dispatch.py:26-30,60-70` — invariant commented, scope documented | Honest per ADR-0004 |
| D3 | `parse_body`/`as_object`/`parse_tags` casts all isinstance-verified first | `dispatch.py:127-131`, `request_fields.py:30-38`, `common_schemas.py:63` | Honest |
| D4 | Handler-registration-as-explicit-wiring; lambdas close over the store | `workgroups.py:91-107` | Earns its place — injectable, tests bind own stores |
| D5 | `schemas.py` re-export shim (69 LOC, 30 names) | 5 src consumers | Live; single import surface |
| D5 | `required_string_list`/`optional_string_list` post-validation filter is dead (every item already validated) | `request_fields.py:113,130` | Cosmetic — folded into G-250 fix surface |
| D6 | `WorkGroupStore.by_name` unbounded | `state.py:106-195` | Bounded by client-created workgroups (no per-request accumulation); execution retention is AU-21 scope |
| D7 | Module-global `OPERATION_HANDLERS` + import-time stores | `dispatch.py:54`, `main.py:133-161` | Single-threaded by construction: async route runs on the event loop; sync handlers contain no `await` (dispatch awaits only `Awaitable` results, `dispatch.py:166-167`); 4000-op asyncio stress consistent (below) |
| D7 | `register_handler` silently overwrites an existing binding | `dispatch.py:73-79` | Closed — that is the documented rebind seam (`main.py:205-219` `reset_query_plane`, `workgroups.py:5-6`); no src double-registration (grep) |
| D8 | 1 MiB body cap: header pre-check + body check compose; a lying-small header is caught by the body check, a lying-large header is rejected without reading | `main.py:184-193`; probe P8b | Sound; cap admits the model's largest legal request (`QueryString` 262144) |
| D8 | Injection surface: `json.loads` only; no yaml/pickle/subprocess/SQL; error messages echo payload values but `json.dumps` escapes and `X-Amzn-Errortype` carries only fixed shape names | `dispatch.py:122-131`, `errors.py:69-78` | Clean |
| D9 | Mutation battery 9/9 killed (below) | — | Strong |
| D9 | 5 plane branches uncovered by the docker-free suites; 2 uncovered everywhere | coverage run below | **G-250 (S4)** |
| D10 | `workgroups.feature`: 5 scenarios — round-trip, duplicate reject, primary-delete reject, partial merge, pagination walk | `tests/bdd/workgroups.feature` | Good depth; POST / covered by `test_main.py` + integration composition/routing |

## Measurements

**P1 — NextToken edge cases** (`offset_page(["a","b","c"], 2, token)`):

| token | result |
|---|---|
| `"-1"` | `([], '1')` — empty page, walk continues |
| `"-5"` | `([], '-3')` — **negative next-token emitted** |
| `" 1 "` | `(['b','c'], None)` — whitespace-padded accepted |
| `"+2"` | `(['c'], None)` — `+`-prefixed accepted |
| `"1.5"`, `"0x1"` | `InvalidRequestException` (the only rejected shapes) |
| `"999…9"` | `([], None)` — past-end, documented |

**P3 — raw-wire constraint bypass** (handler-level probes): `Name="a"×200` →
200; `Name="../escape"` → 200; `BytesScannedCutoffPerQuery=5` → 200;
`TagKey` 200 chars + `TagValue` 300 → 200; `ExecutionRole="not-an-arn"` +
`Description` 2000 chars → 200. Canonical shapes
(`research_repos/aws-cli/.../athena/2017-05-18/service-2.json`):
`WorkGroupName` pattern `[a-zA-Z0-9._-]{1,128}`; `BytesScannedCutoffValue`
`min: 10000000`; `TagKey` `1..128`; `TagValue` `0..256`; `RoleArn` pattern
`^arn:aws[a-z\-]*:iam::\d{12}:role/...$` min 20; `WorkGroupDescriptionString`
max 1024; `NameString` `1..128`. Enforced today: `WorkGroupState` enum
(`state.py:51`), `MaxWorkGroupsCount` 1..50 (`request_fields.py:155-169`),
`Age` 0..10080 (`common_schemas.py:230-237`), `Enabled` required in
`ManagedQueryResultsConfiguration` (`common_schemas.py:330`).

**P2b — managed-results merge**: `Enabled=True` then encryption-only update →
`enabled=True` kept; empty updates → unchanged.

**D7 stress**: 4000 interleaved Create/Update/List/Delete ops via the real
dispatch registry under `asyncio.gather` → store consistent, only `primary`
remains.

**Coverage** (full unit + bdd suites, plane-scoped): 624 stmts, 5 missed —
`dispatch.py:76` (register unknown-op guard — zero tests reference the guard
message anywhere), `common_schemas.py:272` (absent `ResultConfigurationUpdates`
early return — no test posts an update without the member),
`common_schemas.py:193` (Acl payload branch) + `workgroup_schemas.py:116,370`
(managed-results edges) — the latter three have static evidence of live-stack
consumers (`test_awswrangler_consumer.py`, `test_managed_results.py`) but no
docker-free pin. 99% plane coverage.

**Mutation battery** (fail-then-revert, targeted suites): M1 pagination token
emission `<`→`<=` KILLED; M2 int validators accept bool KILLED; M3
`merge_field` drops updates KILLED; M4 `_updated` wipes current KILLED; M5
target segment first-not-last KILLED; M6 errortype header message KILLED; M7
syntax check inverted KILLED; M8 body cap `>`→`>=` KILLED; M9 list max 50→51
KILLED.

**Report notes (no row)**: import-time env validation raises a clear
`ValueError` at uvicorn startup (fail-fast, tested — `test_main.py:152,182`);
empty-string env vars fall through to defaults (`main.py:109`); dispatch's
`logger.exception(json.dumps(...))` attaches a plain-text traceback to a
structured JSON message (`dispatch.py:176-184`); `errors.py:27` base
`status_code = 0` is latent (all 5 subclasses pinned by the parity table);
`TooManyRequestsException` is never raised — protocol vocabulary per ADR-0008,
pinned by `test_errors.py`'s parity table.

## Gaps promoted

| Gap ID | Severity | One-line |
|---|---|---|
| G-248 | S3 | `pagination._token_offset` accepts negative/whitespace/`+`-prefixed tokens — scrambled/empty pages and a negative next-token where real Athena 400s |
| G-249 | S3 | Canonical member constraints (name pattern, cutoff min, tag lengths, RoleArn, description/nameString bounds) unenforced on the raw-wire path — 200 where real Athena rejects |
| G-250 | S4 | Registration drift guard + absent-`ResultConfigurationUpdates` return untested everywhere; 3 more branches docker-free-uncovered; dead list-filter |
