## 03_boto3_query_lifecycle

| feature | status | detail | latency_ms |
|---|---|---|---|
| start→poll→GetQueryExecution (SELECT) + .csv artifact | PASS | 7ad77c1e-0f28-4a41-b26f-5e8448555296 SUCCEEDED DML/SELECT; OutputLocation=s3://nb03-5f81de8c0900/results/7ad77c1e-0f28-4a41-b26f-5e8448555296.csv | 271 |
| GetQueryResults paginates (header on page 0, opaque NextToken) | PASS | 3 manual pages (3+2+1 rows); botocore paginator merged 6 rows losslessly |  |
| batch_get/list executions (unprocessed IDs, paged, newest first) | PASS | unknown id → UnprocessedQueryExecutionIds; MaxResults=1 paginated 2 executions newest-first |  |
| GetQueryRuntimeStatistics (Timeline + Rows shape) | PASS | EngineExecutionTimeInMillis=1 InputBytes=0 |  |
| GetQueryResults on a running execution → 400 | PASS | InvalidRequestException (400): Query has not yet finished. Current state: RUNNING |  |
| StopQueryExecution → CANCELLED | PASS | 8016cde0-64bc-4c04-b157-8f80993cd543 CANCELLED |  |
| stop on a terminal execution (AWS no-ops with 200) | FAIL | InternalServerException (500) on a SUCCEEDED execution; real AWS answers a 200 no-op |  |
| CREATE DATABASE → Glue database + .txt artifact (dialect map) | PASS | 24f86a5a-2c95-4717-a8ae-5fd2a5220b54 SUCCEEDED DDL/CREATE_DATABASE; nb03_ddl_0d29a5ce visible via glue.get_database; .txt + .txt.metadata written | 267 |
| CTAS → -manifest.csv + .metadata + Glue table (parquet at external_location) | PASS | e982a3e8-72cc-4874-858b-d77d549b1091 SUCCEEDED DDL/CREATE_TABLE_AS_SELECT; manifest lists 1 file(s) under ctas-data/ | 265 |
| syntax error → submit-time InvalidRequestException 400 | PASS | InvalidRequestException (400); message starts 'Exception parsing query' |  |
| analysis error → FAILED execution with StateChangeReason | PASS | acb9a638-88d0-40a0-825d-ee7d0adb4c81 FAILED: line 1:15: Table 'hive.nb03_0d29a5ce.no_such_table_xyz' does not exist |  |
| unknown QueryExecutionId → InvalidRequestException 400 | PASS | InvalidRequestException (400) |  |
| missing OutputLocation (primary, no ResultConfiguration) → 400 | PASS | InvalidRequestException (400) |  |
| EXECUTE + ExecutionParameters binds and echoes | PASS | nb03_stmt_0d29a5ce → row 'hello'; ExecutionParameters echoed | 266 |
| qmark ExecutionParameters on a plain query | PASS | SELECT ? with ['42'] → row '42' | 266 |
| EXECUTE failures → FAILED not 400 (missing stmt, ?-count) | PASS | both FAILED with Athena's StateChangeReason phrasing |  |
| ClientRequestToken dedupes retried submissions | GAP | token c2280919… submitted twice → distinct executions 374acd0b…/79983cb8…; AWS returns the original for a retried token |  |
| ResultReuseConfiguration reuses recent results | GAP | second identical run SUCCEEDED (ReusedPreviousResult=None, config echoed=False); AWS re-answers the recent result |  |
| ResultConfiguration.EncryptionConfiguration echoed verbatim | PASS | SSE_S3 + KmsKey echoed on GetQueryExecution | 264 |
| QueryExecutionContext.Catalog=AwsDataCatalog round-trips | PASS | c7aa7e02-826f-4f65-8182-07262f494798 SUCCEEDED; catalog echoed | 266 |
| unknown catalog rejected at submit | GAP | nb03_nocat_0d29a5ce accepted → SUCCEEDED on the hive catalog regardless; real AWS rejects unregistered catalogs |  |
