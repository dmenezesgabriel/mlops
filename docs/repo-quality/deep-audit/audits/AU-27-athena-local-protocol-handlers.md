# AU-27 — athena-local protocol handler family audit (2026-10-07)

Scope: `named_queries.py` (117), `tags.py` (150), `engine_versions.py` (33),
`catalog_metadata.py` (145), `data_catalogs.py` (154) — 599 LOC measured
(`radon raw`, 450 SLOC). Split-fix: these five handler files were claimed by
no plane (AU-20 session, 2026-10-07). Upstream reuse: AU-20's protocol-plane
verdicts cover every shared helper the family calls — `dispatch`
(`register_handler` rebind seam, `parse_body`, error funnel), `request_fields`
validators, `schemas`/`common_schemas` (`parse_tags`, `Tag`,
`DEFAULT_ENGINE_VERSION`), `pagination.offset_page`, `errors` shapes.
`state.py`/`data_catalog_state.py` store contracts and `glue_proxy` internals
are boundaries here — AU-21/AU-25 verify them; this audit checks the handlers
*against* those interfaces. Parity references: vendored
`research_repos/aws-cli/.../athena/2017-05-18/service-2.json` (shapes quoted
below), moto `athena/models.py`, CLI `examples/athena/*.rst`.

## Surface inventory

| Module | Public symbols | Entry points |
|---|---|---|
| `named_queries.py` | `create_named_query`, `get_named_query`, `list_named_queries`, `delete_named_query`, `batch_get_named_query`, `register_named_query_handlers` | 5 handlers via registry |
| `tags.py` | `tag_resource`, `untag_resource`, `list_tags_for_resource`, `register_tag_handlers`, `ATHENA_ARN_PREFIX`, `TAGGABLE_RESOURCE_TYPES` | 3 handlers via registry |
| `engine_versions.py` | `list_engine_versions`, `register_engine_version_handlers` | 1 handler via registry |
| `catalog_metadata.py` | `list_databases`, `get_database`, `list_table_metadata`, `get_table_metadata`, `register_catalog_metadata_handlers`, `MAX_LIST_DATABASES`, `MAX_LIST_TABLE_METADATA`, `MOTO_ENDPOINT_ENV`, `MOTO_ENDPOINT_DEFAULT` | 4 handlers via registry |
| `data_catalogs.py` | `create_data_catalog`, `get_data_catalog`, `list_data_catalogs`, `update_data_catalog`, `delete_data_catalog`, `register_data_catalog_handlers`, `SUPPORTED_CATALOG_TYPES`, `UNSUPPORTED_CATALOG_TYPE`, `LAMBDA_FUNCTION_KEY` | 5 handlers via registry |

18 handlers total, all registered at the composition root (`main.py:135-156`).

## Callgraph

```
POST / (main.athena_endpoint) → dispatch → OPERATION_HANDLERS[op]
  CreateNamedQuery → required_string/optional_string (request_fields)
                   → ensure_workgroup_enabled (state.py:197) → NamedQueryStore.create
  GetNamedQuery / DeleteNamedQuery → required_string → store.get/delete
  ListNamedQueries → member+required_int → store.list → offset_page (G-248 surface)
  BatchGetNamedQuery → required_string_list → store.batch_get
  TagResource/UntagResource/ListTagsForResource → _parse_arn → _resolve_tags
                   → (Tag) parse_tags / required_string_list → in-place tags[:] mutation
  ListEngineVersions → DEFAULT_ENGINE_VERSION (common_schemas) — no store
  ListDatabases/GetDatabase/ListTableMetadata/GetTableMetadata
                   → required_string/optional_max_results/optional_string
                   → _require_glue_catalog (DataCatalogStore.get) → GlueProxy.* → offset_page
  CreateDataCatalog/UpdateDataCatalog → _validated_type → _apply_lambda_defaults
                   → DataCatalogStore.create/update; GetDataCatalog/DeleteDataCatalog → store
  ListDataCatalogs → member+required_int → store.list → offset_page (G-248 surface)
```
Unreachable-looking code: none — vulture clean on all five files; every
helper has a live caller on the callgraph.

## Boundary table

| Boundary | Where | Faked as | Test |
|---|---|---|---|
| moto Glue (botocore client) | `catalog_metadata.py:49-51` (`GlueProxy.for_endpoint`), `glue_proxy.py:158-172` | named fake `CatalogClient` conforming to the `glue_proxy.py:46` Protocol | `tests/unit/test_catalog_metadata.py` (17 tests) |
| uuid4 `NamedQueryId` | `state.py:260` via `store.create` | real (unpinned format) | `test_named_queries.py` |
| env `ATHENA_MOTO_ENDPOINT_URL` | `catalog_metadata.py:50` — read once at registration (composition root), not per request | monkeypatch env | `test_catalog_metadata.py` |
| in-place record mutation (`tags[:] =`) | `tags.py:106,118` | real stores | `test_tags.py` |

No filesystem, subprocess, or RNG boundary in the family; `for_endpoint`
builds a lazy botocore client — no network I/O at registration.

## Dimension findings

| Dim | Suspect / measured | Evidence | Disposition |
|---|---|---|---|
| D1 | **List-op caps unenforced**: `ListNamedQueries` MaxResults=51 accepted (model `MaxNamedQueriesCount` 0..50); `ListDataCatalogs` MaxResults=1 *and* 51 accepted (model `MaxDataCatalogsCount` 2..50); `BatchGetNamedQuery` 51 IDs accepted (model `NamedQueryIdList` 1..50). `catalog_metadata.py:75-77,107-109` already uses `optional_max_results` with the correct 50 cap — the sibling handlers use bare `required_int` (`named_queries.py:60-61`, `data_catalogs.py:92-94`) | probes P-B/P-C/P-D below | **G-251 (S3)** |
| D1 | **Per-op member constraints unenforced** (G-249 class, different fix surface — op shapes, not the shared validators): `CreateNamedQuery` Name 200 chars (model `NameString` 1..128), explicit `Description=""` (model `DescriptionString` min 1), Database/QueryString/WorkGroup/NamedQueryId bounds+patterns all unchecked; `UntagResource` `TagKeys=[""]` accepted (model `TagKey` min 1); catalog ops' `CatalogNameString` pattern/256 and `NameString` 1..128 unchecked | probes P-E/P-F below | **G-252 (S3)** |
| D1 | **`ClientRequestToken` idempotency ignored**: two creates with the same token → two different IDs and two records; model member doc: "If another CreateNamedQuery request is received, the same response is returned and another query is not created. If a parameter has changed … an error is returned." Raw-wire-visible only (botocore auto-fills unique tokens) | `named_queries.py:26-44` (member never read); probe P-G | **G-253 (S3)** |
| D1 | **Tag-count quota unenforced → the no-pagination argument is unsound**: 80 tags attachable via repeated `TagResource` (no cap anywhere), `ListTagsForResource` returns all 80 with no NextToken; `tags.py:129-131` comment asserts "Athena resources hold at most 50 tags" — an invariant nothing enforces (model puts no max on `TagList`; the ≤50 quota is service-side). Visible to botocore clients, not just raw wire | probe P-A below | **G-254 (S3)** |
| D9 | `tags.py:47,52,57` — the three structural malformed-ARN raises (wrong part count, missing `/` separator, empty type/name) uncovered at every layer: unit+bdd coverage 95% missing exactly 47,52,57; integration run also misses them (only the prefix raise `:42` is tested, `test_tags.py:326`) | coverage runs below | **G-255 (S4)** |
| D1 | Unknown-workgroup `CreateNamedQuery` pass-through (`ensure_workgroup_enabled` only rejects DISABLED, `state.py:197-209`) — documented there; moto 500s instead (`models.py:537` bare `work_groups[workgroup]` KeyError); real-Athena behavior unverifiable from vendored material | `state.py:202-205` | Suspect — report only (documented decision, no spec citation either way) |
| D1 | Duplicate tag keys within one `Tags` list accepted (`parse_tags` never dedups); moto also accepts (`models.py:40-43` last-wins) | `common_schemas.py:54-79` | G-249 surface (tag constraints) — reused, no new row |
| D1 | moto upsert *moves* an updated key to the end (`models.py:40-43` filter+extend); emulator keeps the original position (`tags.py:104-106` dict update) — tag order unspecified by AWS; both self-consistent | `tags.py:104-106` | Suspect — report only (order not part of the wire contract) |
| D1 | `DeleteCatalogOnly` member declared by the model, ignored by the handler; CLI example never passes it; real delete-associated-metadata semantics unverifiable | `data_catalogs.py:126-130` | Suspect — report only |
| D1 | `WorkGroup` member ignored on the four metadata ops (model declares it on all four); real Athena's use (engine-version context) unverifiable | `catalog_metadata.py:68-135` | Suspect — report only |
| D1 | `ListTagsForResource` ignores a *provided* NextToken (garbage token → 200 + all tags; real Athena 400s per the G-248 class) — same fix surface as G-254 (paginate properly, then tokens get validated) | `tags.py:122-132` | Folded into G-254 |
| D1 | LAMBDA catalog without `function` accepted (`_apply_lambda_defaults` only derives when `function` present); real-Athena requirement unverifiable from vendored material | `data_catalogs.py:50-63` | Suspect — report only |
| D1 | `ListNamedQueries` MaxResults=0 (model min 0 — legal) → `offset_page` treats ≤0 as "no limit" (`pagination.py:42`, documented) → returns everything; real-Athena 0-semantics ambiguous | `pagination.py:29-31` | Suspect — report only |
| D2 | `list_databases`/`list_table_metadata` convert **all** Glue objects before paging (`catalog_metadata.py:79,111-114`) | probe P-I: 0.23→2.15→24.14 ms and 0.36→3.26→39.30 ms at n=10²/10³/10⁴ (max_results=1), slope ≈ 1.01 | Linear — innocent (same shape as the store lists AU-20 accepted) |
| D3 | No `cast`/`Any` in the five files; `payload: dict[str, object] | None` + `dict[str, object]` returns are honest | grep clean | Honest |
| D4 | Lambda-registration wiring closes over stores — same pattern as `workgroups.py` | `named_queries.py:97-117` etc. | AU-20 verdict reused: earns its place (injectable, tests bind own stores) |
| D5 | Names specific (`_parse_arn`, `_resolve_tags`, `_apply_lambda_defaults`, `_require_glue_catalog`); files 33–154 LOC; `register_catalog_metadata_handlers` 29 LOC (4 registrations) matches the sibling style | reading | Clean |
| D6 | Handlers stateless; per-record `tags` lists grow only via client calls (no per-request accumulation); store retention is AU-21 scope | reading | Innocent here |
| D7 | In-place `tags[:]` mutation is a new shared-state touchpoint vs AU-20's stress | construction: async route → event loop, sync handlers await-free (`dispatch.py:166-167` — AU-20 verdict reused); 2000-op gather stress over Tag/Untag/ListTags/ListDataCatalogs → final state consistent, no duplicate keys (below) | Single-threaded by construction — holds |
| D8 | ARN parsing raises only (no shell/SQL/template surface); `Expression` passes to Glue as a botocore kwarg (`glue_proxy.py:194-196`), no interpolation; error messages echo ARN values but `json.dumps` escapes (AU-20 verdict) | `tags.py:35-60`, `catalog_metadata.py:106` | Clean |
| D10 | bdd scenarios: named_queries 7, tags 5, data_catalogs 8, catalog_metadata 7, engine_versions 1 (28 total) + integration suites per family (real HTTP + moto) | `tests/bdd/*.feature` | Good depth |

## Measurements

**P-B/P-C/P-D — cap probes** (handler-level, real stores): listed in the D1
rows above — 51/1/51/51 all accepted where the model declares 0..50, 2..50,
1..50.

**P-E/P-F — member-constraint probes**: `TagKeys=[""]` → no-op success
(model `TagKey` min 1); `Name="n"×200` → record created (model 1..128);
explicit `Description=""` → stored as `""` (model min 1).

**P-G — idempotency probe**: same 32-char `ClientRequestToken` twice → two
different `NamedQueryId`s, two records (model doc quoted in the D1 row).

**P-A — tag-count probe**: 2× `TagResource` with 40 fresh keys each → 80 tags
on `primary`; `ListTagsForResource` → all 80, `NextToken` absent. The
`tags.py:129-131` comment's "at most 50 tags" invariant is not enforced by
any code path.

**P-I — D2 scaling** (fake `CatalogClient`, max_results=1): table above —
linear, slope ≈ 1.01.

**D7 stress**: 2000 ops (500× Tag/Untag/ListTags/ListDataCatalogs) through
the real async `dispatch` under `asyncio.gather` → final tag state consistent
(0 tags — each tag added at i≡0 is removed at i≡1; no duplicates, no
corruption).

**Coverage** (unit+bdd, five modules scoped): 241 stmts, 3 missed —
`tags.py:47,52,57` only (99%). Integration run (4 family suites, real
HTTP+moto): misses `tags.py:42,47,52,57,70,78,101` — union across all layers
leaves exactly 47,52,57 uncovered everywhere.

**Mutation battery** (fail-then-revert, targeted suites) — 5/5 KILLED:
M1 `next_token_out` gate removed (always emit NextToken) →
`test_list_named_queries_returns_ids_by_workgroup` failed; M2 tag upsert
inverted (old value wins) → `test_tag_resource_replaces_existing_key`
failed; M3 pinned engine values swapped → bdd
`test_listengineversions_returns_the_pinned_engine` failed; M4 GLUE gate
inverted → `test_list_databases_returns_database_list` failed; M5 enum check
inverted → `test_create_glue_data_catalog_returns_payload` failed.

## Gaps promoted

| Gap ID | Severity | One-line |
|---|---|---|
| G-251 | S3 | List-op caps unenforced: ListNamedQueries 0..50, ListDataCatalogs 2..50, BatchGetNamedQuery list 1..50 — bare `required_int`/`required_string_list` where `optional_max_results` already exists |
| G-252 | S3 | Per-op member constraints unenforced across the family (NameString/DescriptionString/DatabaseString/QueryString/NamedQueryId/CatalogNameString/NameString/TagKey bounds+patterns) — G-249 class at the op layer |
| G-253 | S3 | `ClientRequestToken` idempotency ignored on CreateNamedQuery — same token → two records, two IDs (model doc: same response, no second create) |
| G-254 | S3 | Tag-count quota unenforced → 80 tags attachable, ListTagsForResource returns all with no NextToken — the `tags.py:129-131` no-pagination argument rests on an invariant nothing enforces |
| G-255 | S4 | `tags.py:47,52,57` structural malformed-ARN raises untested at every layer |
