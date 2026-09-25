## 03_boto3_query_lifecycle

| feature | status | detail | latency_ms |
|---|---|---|---|
| start→poll→GetQueryExecution (SELECT) + .csv artifact | PASS | 576a1b87-08c2-4ff4-9021-9f9ee8c7fb6c SUCCEEDED DML/SELECT; OutputLocation=s3://nb03-9ddf0773042c/results/576a1b87-08c2-4ff4-9021-9f9ee8c7fb6c.csv | 295 |
| GetQueryResults paginates (header on page 0, opaque NextToken) | PASS | 3 manual pages (3+2+1 rows); botocore paginator merged 6 rows losslessly |  |
| batch_get/list executions (unprocessed IDs, paged, newest first) | PASS | unknown id → UnprocessedQueryExecutionIds; MaxResults=1 paginated 2 executions newest-first |  |
| GetQueryRuntimeStatistics (Timeline + Rows shape) | PASS | EngineExecutionTimeInMillis=0 InputBytes=0 |  |
| GetQueryResults on a running execution → 400 | PASS | InvalidRequestException (400): Query has not yet finished. Current state: RUNNING |  |
| StopQueryExecution → CANCELLED | PASS | 978fe72d-998c-42f0-9aee-b23a1d54b601 CANCELLED |  |
| stop on a terminal execution (AWS no-ops with 200) | FAIL | InternalServerException (500) on a SUCCEEDED execution; real AWS answers a 200 no-op |  |
| CREATE DATABASE → Glue database + .txt artifact (dialect map) | PASS | b97bb372-52d2-4182-b36a-f7ed07161cc3 SUCCEEDED DDL/CREATE_DATABASE; nb03_ddl_b9251fd6 visible via glue.get_database; .txt + .txt.metadata written | 292 |
| CTAS → -manifest.csv + .metadata + Glue table (parquet at external_location) | PASS | 8066cf93-3624-489f-b073-42ef23a960f3 SUCCEEDED DDL/CREATE_TABLE_AS_SELECT; manifest lists 1 file(s) under ctas-data/ | 282 |
| syntax error → submit-time InvalidRequestException 400 | PASS | InvalidRequestException (400); message starts 'Exception parsing query' |  |
| analysis error → FAILED execution with StateChangeReason | PASS | fcbf6288-da14-4c13-b37a-09a8ebe81f8c FAILED: line 1:15: Table 'hive.nb03_b9251fd6.no_such_table_xyz' does not exist |  |
| unknown QueryExecutionId → InvalidRequestException 400 | PASS | InvalidRequestException (400) |  |
| missing OutputLocation (primary, no ResultConfiguration) → 400 | PASS | InvalidRequestException (400) |  |
| EXECUTE + ExecutionParameters binds and echoes | PASS | nb03_stmt_b9251fd6 → row 'hello'; ExecutionParameters echoed | 283 |
| qmark ExecutionParameters on a plain query | PASS | SELECT ? with ['42'] → row '42' | 286 |
| EXECUTE failures → FAILED not 400 (missing stmt, ?-count) | PASS | both FAILED with Athena's StateChangeReason phrasing |  |
| ClientRequestToken dedupes retried submissions | GAP | token d56e40d9… submitted twice → distinct executions 9bc3ba8e…/90df1720…; AWS returns the original for a retried token |  |
| ResultReuseConfiguration reuses recent results | GAP | second identical run SUCCEEDED (ReusedPreviousResult=None, config echoed=False); AWS re-answers the recent result |  |
| ResultConfiguration.EncryptionConfiguration echoed verbatim | PASS | SSE_S3 + KmsKey echoed on GetQueryExecution | 286 |
| QueryExecutionContext.Catalog=AwsDataCatalog round-trips | PASS | 29da55c3-4111-466e-811f-2bae86093730 SUCCEEDED; catalog echoed | 283 |
| unknown catalog rejected at submit | GAP | nb03_nocat_b9251fd6 accepted → SUCCEEDED on the hive catalog regardless; real AWS rejects unregistered catalogs |  |
