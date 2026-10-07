# AU-24 — athena-local execution plane audit (2026-10-07)

Scope: `submission.py` (458), `executor.py` (358), `query_executions.py`
(378), `prepared_execution.py` (366), `statement_classification.py` (175) —
1735 LOC measured (`radon raw`; 1128 SLOC). Upstream reuse: AU-20 protocol
verdicts (`request_fields` validators, `dispatch` await semantics,
single-threaded route argument), AU-21 state-plane contracts
(`ExecutionStore.create/find_by_request_token/find_reusable`, TTL+cap
retention, `transition_to` terminal-immutability, `find_reusable` 16.1 ms @
10⁴), AU-22 SQL-plane helpers (`strip_comments`, `quoted_end`,
`balanced_span`), AU-23 iceberg routing. Downstream: `trino_client.py`,
`output_targets.py`, `artifacts.py`, `query_results.py`, `result_shapes.py`
are AU-25 scope — treated as boundaries and faked with the existing named
fakes. Parity references: `research_repos/aws-cli/.../athena/service-2.json`
(the canonical model, byte-pinned by `canonical_model.feature`), pinned
botocore 1.42.97, awswrangler `_read.py:217-221`/`_utils.py:196`, ADR-0009.

## Surface inventory

| Module | Public symbols | Entry points |
|---|---|---|
| `submission.py` | `SubmissionPlanner` (`resolve_record`, `create_record`, `prepare`), `StartRequest`, `PreflightVerdict`, `PreparedSubmission`, `StatementClient` (Protocol), `ManifestSnapshotSource` (Protocol) | ★`SubmissionPlanner.resolve_record/prepare` (executor.py:150,153) |
| `executor.py` | `QueryExecutor` (`start`, `cancel`, `ensure_query_finished`), `ResultArtifactWriter` (Protocol), `ArtifactWriteError`, `DEFAULT_MAX_CONCURRENT_QUERIES` | ★`QueryExecutor.start` (query_executions.py:218), ★`cancel` (:323), ★`ensure_query_finished` (query_results.py) |
| `query_executions.py` | 7 handlers + `register_query_execution_handlers` | ★handlers bound in `main.py` (dispatch registry) |
| `prepared_execution.py` | `resolve_execute_statement`, `parse_execute_statement`, `bind_parameters`, `encode_execution_parameter`, `ExecuteParts`, `ExecuteResolution`, `ParameterCountError` | ★`resolve_execute_statement` (query_executions.py:212) |
| `statement_classification.py` | `classify_statement`, `normalize_statement_text`, `artifact_output_kind`, `StatementClassification`, statement-type constants | consumed by `query_executions`, `submission`, `execution_record` (AU-21) |

## Callgraph

```
main.py register_query_execution_handlers
StartQueryExecution (query_executions.py:170)
  → resolve_execute_statement (prepared_execution.py:201)
      → parse_execute_statement (:117) → strip_comments (AU-22 verdict)
          → _parse_statement_name (:295) / _split_top_level_values (:337)
      → _stored_statement_or_failure (:266) → PreparedStatementStore.get (AU-21)
      → _bind_or_fail (:242) → bind_parameters (:150)
          → _count_placeholders (:331) / _placeholder_segments (:319)
      → classify_statement (statement_classification.py:108) → _leading_tokens (:139)
  → _effective_result_configuration (:124) → workgroup record (AU-20 verdict)
  → QueryExecutor.start (executor.py:103) → _submit (:149)
      → SubmissionPlanner.resolve_record (submission.py:179)
          → _request_token_replay (:318) → ExecutionStore.find_by_request_token (AU-21)
          → create_record (:206) → ExecutionStore.create (AU-21)
          → _reusable_source (:349) → ExecutionStore.find_reusable (AU-21)
      → SubmissionPlanner.prepare (:241)
          → _map_statement (:267) → unload_trino_submission / add_partition_trino_call (AU-22)
              → _mapped_dialect (:297) → iceberg_trino_submission (AU-23) / to_trino_dialect (AU-22)
          → _capture_manifest (:381) → ManifestSnapshotSource.capture   ← BOUNDARY (AU-25)
          → _preflight (:418) → StatementClient.submit_statement / fetch_next  ← BOUNDARY (AU-25)
      → create_record (:206) → ExecutionStore.create
      → _dispatch (:164) → asyncio.create_task(_execute)
StopQueryExecution (query_executions.py:315) → QueryExecutor.cancel (executor.py:171)
  → _stop_statement (:341) → StatementClient.cancel                     ← BOUNDARY
GetQueryExecution / BatchGetQueryExecution / ListQueryExecutions (:258,:268,:288)
  → ExecutionStore.get/batch_get/list_execution_ids (AU-21 verdicts)
QueryExecutor._execute (executor.py:202)
  → _poll_to_end (:232) → StatementClient.fetch_next
  → _partition_exists_noop (:286)
  → _complete (:256) → to_athena_result_shape (AU-25) / cache_result_page
      → _unload_cleanup_error (:302) → drop_table  |  ResultArtifactWriter.write ← BOUNDARY (AU-25)
```

Unreachable-looking code: `query_executions.py:66-67` (`payload is None` arm of
`_optional_client_request_token`) is unreachable from the handler — line 204
`required_string(payload, "QueryString")` fires first; vulture clean otherwise.

## Boundary table

| Boundary | Where | Faked as | Test |
|---|---|---|---|
| Trino statement protocol (submit/fetch/DELETE) | `submission.py:433-455`, `executor.py:248,347` | `ScriptedStatementClient`, `GatedStatementClient`, `TerminalStatementClient` (named fakes) | `test_executor*.py`, `test_start_query_execution.py`, `test_start_execution_reuse.py` |
| Glue/S3 manifest snapshot | `submission.py:411` | `RecordingSnapshotter` (named fake) | `test_executor_submit.py`, `test_executor_unload.py` |
| S3 artifact writer | `executor.py:278` | `RecordingWriter`, `FailingWriter` (named fakes) | `test_executor.py`, `test_executor_completion.py` |
| Execution store | `submission.py`/`executor.py` | real in-memory `ExecutionStore` (AU-21 verdict: race-free single-loop, TTL+cap) | all plane suites |

No filesystem, network, subprocess, env, or RNG boundary inside the plane —
the three ports above are the only external touches.

## Dimension findings

| Dim | Suspect / measured | Evidence | Disposition |
|---|---|---|---|
| D1 | **Concurrent same-token `StartQueryExecution` double-executes** — `resolve_record`'s token lookup is sync, but `create_record` runs after `prepare`'s awaits; two in-flight retries of the same token both miss the store and both submit. The store's first-wins `setdefault` keeps the map coherent but the duplicate record + Trino submission exist; the retry answers its *own* new id. Model: "the same response is returned and another query is not created" | probe P-1; `submission.py:179-204`, `executor.py:149-154`, `executions.py:132-139`; `test_execution_store.py:82-96` pins the duplicate create | **G-268 (S1)** |
| D1 | **Cancel during the artifact write kills the task with an unretrieved `ValueError`** — `_complete` awaits `writer.write` (the only await before the terminal transition), so a `StopQueryExecution` landing there transitions CANCELLED first; the resumed `transition_to(SUCCEEDED)` then raises CANCELLED→SUCCEEDED (terminal immutable). The task dies unobserved (`_tasks` pop callback retrieves nothing); the artifacts are written for a CANCELLED record | probe P-2; `executor.py:277-284`, `execution_record.py:145-151`, `executor.py:167-169` | **G-269 (S1)** |
| D1 | **Cancel of a QUEUED execution never stops the already-submitted engine statement** — submission happens at preflight (ADR-0009 #2), before the semaphore; `active_next_uri` is only set once the task starts, so `_stop_statement` no-ops and no DELETE is ever issued. The Trino statement runs to completion (DML writes land) while the wire reports CANCELLED; the ADR-0009 model ("RUNNING once dispatched to Trino") and the cancel test's "never executed" comment both misdescribe the real dispatch point | probes P-3/P-4; `executor.py:205-215,341-351`, `submission.py:433-457`, `test_executor_cancel.py:74-80` | **G-270 (S1)** |
| D1 | **`ClientRequestToken` bounded 1..36 where the model declares 32..128** (`IdempotencyToken`) — 37..128-char tokens are rejected through a real boto3 client where real Athena accepts them; 1..31-char tokens are accepted on the raw wire where real Athena 400s (botocore enforces min 32 client-side, so only the over-length side is client-visible). The comment and the pinning test both cite the wrong bound | probe P-5; `query_executions.py:57-59,62-77`; `test_start_execution_reuse.py:265-287` | **G-271 (S3)** |
| D1 | **`StartQueryExecution` op-layer member bounds unenforced** — `ExecutionParameters` member max 1024 and list min 1 (model) both unchecked: a 2000-char member is accepted end-to-end (client-visible; botocore does not length-check list members), an empty list is accepted and silently treated as absent; `QueryExecutionContext.Database` 1..255 unchecked (300 chars accepted client-visible; `""` accepted raw-wire) — G-249/G-252 class at this op's parse sites | probe P-5; `query_executions.py:87-90,210`; `request_fields.py:116-131` | **G-272 (S3)** |
| D1 | **Query-plane list bounds diverge from the model** — `BatchGetQueryExecution` accepts 51 IDs (model `QueryExecutionIdList` 1..50; 51 unprocessed items returned, client-visible) and `ListQueryExecutions` rejects `MaxResults=0` (model `MaxQueryExecutionsCount` 0..50; `optional_max_results` is 1..N) — the two directions of the G-251 class | probe P-5; `query_executions.py:271,302`; `request_fields.py:99-113,155-169` | **G-273 (S3)** |
| D1 | **Parenthesized top-level queries misclassify as UTILITY/None → `.txt` artifact** — `_leading_tokens` sees `(SELECT`, matches no statement set. Live-stack `(SELECT 1) UNION (SELECT 2)` reports `StatementType=UTILITY`, `SubstatementType=None`, OutputLocation `.txt` where the control `WITH … SELECT … UNION (SELECT 2)` reports DML/SELECT `.csv`; wrangler's read path returns an **empty DataFrame** for any non-`.csv` location (`_read.py:217-221`), so a real consumer silently reads zero rows. Report notes: `WITH … INSERT/DELETE` classify as DML/SELECT too, but Trino rejects those shapes at submit (probe P-6) so no record/wire surface exists; `CREATE OR REPLACE VIEW` → `CREATE_OR` and `EXPLAIN (TYPE …)` → `EXPLAIN_` are free-form-field naming nits | probe P-6; `statement_classification.py:108-126,139-141,143-147` | **G-274 (S3)** |
| D1 | **Backtick spans are not lexed by the placeholder/USING scanners** — `_PLACEHOLDER_SCAN_RE` isolates `'…'`, `"…"`, comments but not `` `…` `` (Athena's identifier quoting; `sql_lexing.quoted_identifier` knows it), so ``bind_parameters("SELECT `a?b` FROM t WHERE x = ?", ["1","2"])`` splices into the identifier (``SELECT `a(1)b` FROM t WHERE x = (2)`` — corrupt SQL) and the 1-value case raises `ParameterCountError: expected 2`; `_split_top_level_values` splits a comma inside backticks (``EXECUTE st USING `a,b` `` → 2 values) though its docstring says quoted identifiers stay whole (the `"a,b"` control splits correctly) | probe P-7; `prepared_execution.py:77-80,337-366` | **G-275 (S3)** |
| D2 | Linear across the plane: `classify_statement` 0.006/0.043/0.393 ms, `normalize_statement_text` 0.007/0.050/0.513 ms, `bind_parameters` 0.122/0.866/9.154 ms, `resolve_execute_statement` 0.143/1.342/13.558 ms at n=10²/10³/10⁴ (slopes 0.89-0.99). `bind_parameters` re-runs `_placeholder_segments` (count + bind = two passes) — constant factor, no row | P-8 table | Clean |
| D3 | No `cast`/`Any`/`type: ignore`/`Dict` in the five modules (grep clean); `StartRequest`/`_MappedSubmission`/`PreparedSubmission` concretely typed; `assert prepared.page is not None` (executor.py:158-160) is an invariant narrowing with a comment, not a silent cast | grep + reading | Honest |
| D4 | Ports at real seams (`StatementClient`, `ManifestSnapshotSource`, `ResultArtifactWriter` each have production + fake implementations; deleting any breaks a caller); `SubmissionPlanner` split earns its place (ADR-0009 submit-path ownership, F.I.R.S.T. lifecycle tests). Note: the semaphore bounds *poll tasks*, not engine submissions (each start POSTs before the semaphore) — ADR-0009's "bounded … to protect the dev machine" holds only for emulator-side work | reading + P-4 (submission_count==2 at cancel) | Earns their place; report note |
| D5 | Files 458/358/378/366/175 LOC (< 500); max cyclomatic rank B (`start_query_execution` B(10), `_effective_result_configuration` B(8) — linear guard chains, AU-22 anti-churn precedent); `create_record`'s 34-line kwarg wall is the already-open G-259 (AU-21) — not re-promoted; `_stored_statement_or_failure`'s success-path classification is computed then discarded (dead field on one arm) | radon cc/raw; reading | Clean (G-259 referenced) |
| D6 | In-flight bound is the live count (documented in `executions.py`): 1000 concurrent starts → 1000 records + 1000 parked tasks, tracemalloc +4134 KB (≈4.2 KB/execution); after drain `_tasks`=0 and all SUCCEEDED; 2000 sequential executions → `_tasks`=0, store 2000 (cap 10 000), +4332 KB (≈2.2 KB/record incl. cached rows). No leak in the task map; no admission control beyond the semaphore (report note — dev-machine scope) | P-9 | Documented bound |
| D7 | **Three measured races** (P-1…P-4): same-token duplicate execution; cancel-vs-writer unretrieved `ValueError`; QUEUED-cancel leaves the engine statement running (stress: 120 starts, 40 cancelled → only 3 DELETEs — the records parked in a poll fetch; the 37 QUEUED ones were never stopped). Corroboration: 120 concurrent starts, 40 cancelled mid-flight → 0 task exceptions, 0 tasks left, states exactly {CANCELLED×40, SUCCEEDED×80}; single-loop mutation discipline holds everywhere except the two await windows above | P-1…P-4 | **G-268/G-269/G-270 (S1)** |
| D8 | Escaping verified: quote-doubling (`O'Brien` → `'O''Brien'`), injection-shaped values quoted, documented expression forms verbatim (parity contract, module docstring), backslash literal (Trino probe OK), `?` inside literals/comments/double-quoted identifiers never bound (probe P-7 controls); no fs/subprocess surface in-plane | P-7 + live-Trino parse probe | Clean |
| D9 | Coverage (full suite: unit+bdd+live-stack integration, plane-scoped): 571 stmts, 8 missed, 99% — `executor.py` 97% (246 cancel-mid-poll return, 251 poll fetch-error → FAILED, 338-339 unload-drop swallow), `prepared_execution.py` 98% (304, 311 malformed-name raises), `query_executions.py` 99% (67 payload-None arm, also unreachable from the handler), `statement_classification.py` 98% (169 single-token utility); `submission.py` 100%. Mutation battery 13/14 killed; M-2 (`_poll_to_end` CANCELLED check dropped) survived the full suite | P-10 | **G-276 (S4)** |
| D10 | `managed_results.feature` (1 scenario — Start on a managed workgroup) + `query_executions.feature` (3 — inline GetQueryResults pagination) + `canonical_model.feature` (3 — model parity); live-stack suites pin every op: AWS-CLI doc examples start/get/list/batch-get/stop + get-results (`test_aws_cli_query_executions.py`), result reuse (2), error mapping (2), inline results (5), managed (3), output location (2), prepared execution (4), UNLOAD consumer (6), awswrangler consumer (4). Stop/List/BatchGet have no bdd scenario — covered live, note only | `tests/bdd/*.feature`, `tests/integration/*` | Good depth |

## Measurements

**P-1 — concurrent same-token submit** (`asyncio.gather` of two identical
starts, 32-char token, scripted client with a submit await):

| probe | result |
|---|---|
| two concurrent starts, same token | ids differ (two fresh UUIDs), `same response: False` |
| Trino submissions / store records | 2 / 2 (both SUCCEEDED) |
| sequential retry after completion | same id as the first, 0 new submissions (replay works) |

**P-2 — cancel during the artifact write** (gated writer; cancel lands inside
`await writer.write`):

| probe | result |
|---|---|
| cancel | record → CANCELLED (200) |
| task outcome | `ValueError: Cannot transition query execution … from CANCELLED to SUCCEEDED` (unretrieved) |
| writer | completed anyway; record stays CANCELLED |

**P-3 — QUEUED cancel** (semaphore=1, first execution parked in a poll fetch,
second QUEUED):

| probe | result |
|---|---|
| submissions at cancel time | 2 — the QUEUED statement was already POSTed to Trino |
| DELETE calls for the queued statement | none |
| final states | first SUCCEEDED, queued CANCELLED |

**P-4 — mixed stress** (120 concurrent starts, semaphore=8, gated poll
fetches, 40 cancelled after they queued):

| probe | result |
|---|---|
| elapsed / submissions | 0.058 s / 120 |
| states | CANCELLED×40, SUCCEEDED×80 |
| DELETE calls | 3 (only the records parked in a poll fetch at cancel time) |
| tasks left / exceptions | 0 / none |

**P-5 — op-layer constraint probes** (handler-level real stores + live boto3
against :5001):

| probe | model | emulator |
|---|---|---|
| token 10/31 chars | min 32 → 400 | accepted (raw wire; botocore blocks client-side) |
| token 37/40/128 chars | ≤128 → accept | 400 "between 1 and 36 characters" (client-visible at 40) |
| BatchGet 51 ids | max 50 → 400 | 200, 51 unprocessed (client-visible) |
| `ExecutionParameters=["x"*2000]` | member ≤1024 | accepted end-to-end (client-visible) |
| `ExecutionParameters=[]` | list min 1 | accepted, treated as absent |
| `Database="x"*300` | ≤255 | accepted (client-visible) |
| `Database=""` | min 1 | accepted (raw wire) |
| `MaxResults=0` | 0..50 | 400 (client-visible) |

**P-6 — classification on the live stack** (boto3 → :5001; Trino :8485):

| probe | result |
|---|---|
| `(SELECT 1) UNION (SELECT 2)` | SUCCEEDED `UTILITY/None`, `…txt` |
| `(VALUES 1) UNION (VALUES 2)` | SUCCEEDED `UTILITY/None`, `…txt` |
| control `WITH … SELECT … UNION (SELECT 2)` | SUCCEEDED `DML/SELECT`, `…csv` |
| `WITH x AS (SELECT 1) INSERT INTO t SELECT * FROM x` | 400 `Exception parsing query` (Trino `SYNTAX_ERROR: mismatched input 'INSERT'`) — no record, so the WITH-collapse consequence is unreachable |
| `CREATE OR REPLACE VIEW v AS SELECT 1` | DDL/`CREATE_OR` (naming nit) |
| `EXPLAIN (TYPE DISTRIBUTED) SELECT 1` | UTILITY/`EXPLAIN_` (naming nit) |

**P-7 — backtick scanners + escaping** (`prepared_execution`):

| probe | result |
|---|---|
| ``bind_parameters("SELECT `a?b` FROM t WHERE x = ?", ["1","2"])`` | ``SELECT `a(1)b` FROM t WHERE x = (2)`` — corrupt |
| same, 1 value | `ParameterCountError: expected 2 but found 1` |
| ``parse_execute_statement("EXECUTE st USING `a,b`")`` | ``values=['`a', 'b`']`` (control `"a,b"` → one value) |
| `?` in `'…'` / `--` / `/* */` / `"…"` | never bound (controls pass) |
| `O'Brien` → `'O''Brien'`; `x'; DROP TABLE t; --` → quoted; `CAST(…)` verbatim | escaping holds; all emitted literals parse on live Trino |

**P-8 — D2 scaling** (min of 3, n = 10²/10³/10⁴):

| function | n=100 | n=1000 | n=10000 | slope |
|---|---|---|---|---|
| `classify_statement` | 0.006 ms | 0.043 ms | 0.393 ms | 0.89 |
| `normalize_statement_text` | 0.007 ms | 0.050 ms | 0.513 ms | 0.94 |
| `bind_parameters` (n markers) | 0.122 ms | 0.866 ms | 9.154 ms | 0.94 |
| `resolve_execute_statement` (n params) | 0.143 ms | 1.342 ms | 13.558 ms | 0.99 |

**P-9 — D6 memory** (tracemalloc):

| probe | result |
|---|---|
| 1000 concurrent starts (semaphore 4) | 1000 records + 1000 tasks, +4134 KB (≈4.2 KB/execution) |
| after gate opens | `_tasks`=0, all SUCCEEDED, −1098 KB |
| 2000 sequential executions | `_tasks`=0, store 2000 (cap 10 000), +4332 KB (≈2.2 KB/record) |

**P-10 — coverage + mutation battery** (full suite = unit + bdd + live-stack
integration, 1362 passed / 2 skipped in 226.7 s):

| module | stmts | missed | % | missed lines |
|---|---|---|---|---|
| `submission.py` | 141 | 0 | 100% | — |
| `executor.py` | 141 | 4 | 97% | 246, 251, 338-339 |
| `query_executions.py` | 101 | 1 | 99% | 67 |
| `prepared_execution.py` | 125 | 2 | 98% | 304, 311 |
| `statement_classification.py` | 63 | 1 | 98% | 169 |
| **plane** | **571** | **8** | **99%** | |

Mutation battery (fail-then-revert; unit+bdd, survivors re-run full suite):

| Mutant | Flip | Result |
|---|---|---|
| M-1 | `_execute` QUEUED guard dropped | KILLED |
| M-2 | `_poll_to_end` CANCELLED check dropped (`executor.py:245`) | **SURVIVED (full suite)** |
| M-3 | poll fetch-error CANCELLED guard dropped | KILLED |
| M-4 | `_partition_exists_noop` `and`→`or` | KILLED |
| M-5 | token-replay `same_request` check dropped | KILLED |
| M-6 | preflight nextUri fetch skipped | KILLED |
| M-7 | preflight row fold dropped | KILLED |
| M-8 | `ClientRequestToken` bound check dropped | KILLED |
| M-9 | `bind_parameters` paren-wrap dropped | KILLED |
| M-10 | WITH→SELECT arm dropped | KILLED |
| M-11 | CTAS `AS` detection dropped | KILLED |
| M-12 | UNLOAD dropped from manifest gate | KILLED |
| M-13 | `QueryString` length bound dropped | KILLED |
| M-14 | `_execute` error branch dropped | KILLED |

M-2 sits exactly on the uncovered cancel-mid-poll return (`executor.py:246`):
no test lands a cancel while a fetch whose page still carries a `next_uri` is
in flight.

**Report notes (no row)**: the semaphore bounds poll tasks, not engine
submissions (each `start` POSTs at preflight — ADR-0009 "protect the dev
machine" holds only for emulator-side work; real Athena's active-query quota
has no counterpart); `_stored_statement_or_failure`'s success-path
classification is dead; `query_executions.py:67` is handler-unreachable;
`WITH`-collapse classification (`WITH … INSERT/DELETE` → DML/SELECT) has no
reachable harm — Trino rejects those shapes at submit before any record
exists (P-6); the `executor._execute` `assert` is an invariant narrowing.

## Gaps promoted

| Gap ID | Severity | One-line |
|---|---|---|
| G-268 | S1 | Concurrent same-token `StartQueryExecution` double-executes — two in-flight retries both miss the token lookup (create happens after `prepare`'s awaits) → 2 ids, 2 Trino submissions, 2 records; sequential retry replays correctly |
| G-269 | S1 | Cancel during the artifact write dies as an unretrieved `ValueError` — `await writer.write` is the only pre-terminal await, so a `StopQueryExecution` landing there makes `transition_to(SUCCEEDED)` raise CANCELLED→SUCCEEDED inside a task nobody awaits; artifacts are written for a CANCELLED record |
| G-270 | S1 | Cancel of a QUEUED execution never stops the already-submitted engine statement — `active_next_uri` is set only after the semaphore while submission happens at preflight, so `_stop_statement` no-ops and the Trino statement runs to completion (DML writes land) while the wire reports CANCELLED |
| G-271 | S3 | `ClientRequestToken` bounded 1..36 where the model declares `IdempotencyToken` 32..128 — 37..128-char tokens 400 through a real boto3 client; 1..31-char tokens accepted on the raw wire; the pinning test cites the wrong bound |
| G-272 | S3 | `StartQueryExecution` op-layer member bounds unenforced — `ExecutionParameters` member ≤1024 and list min 1 unchecked (2000-char member accepted client-visible; `[]` treated as absent), `QueryExecutionContext.Database` 1..255 unchecked (300 chars accepted) |
| G-273 | S3 | Query-plane list bounds diverge from the model — `BatchGetQueryExecution` accepts 51 IDs (model 1..50, client-visible) and `ListQueryExecutions` rejects `MaxResults=0` (model 0..50, client-visible) |
| G-274 | S3 | Parenthesized top-level queries classify `UTILITY/None` → `.txt` artifact — live `(SELECT 1) UNION (SELECT 2)` vs DML/SELECT `.csv` control; wrangler's read path returns an empty DataFrame for non-`.csv` locations |
| G-275 | S3 | Backtick spans unlexed by the placeholder/USING scanners — `?` inside `` `…` `` is counted and spliced (``SELECT `a(1)b`…``), ``EXECUTE … USING `a,b` `` splits one expression into two, though `sql_lexing` and the function docstring both treat quoted identifiers as atomic |
| G-276 | S4 | Guard-arm test depth — 8/571 plane stmts uncovered (cancel-mid-poll return, poll fetch-error → FAILED, unload-drop swallow, malformed EXECUTE names, payload-None arm, single-token utility) and M-2 (`_poll_to_end` CANCELLED check) survives the full suite |
