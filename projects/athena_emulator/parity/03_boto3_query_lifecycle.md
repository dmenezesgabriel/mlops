## 03_boto3_query_lifecycle

| feature | status | detail | latency_ms |
|---|---|---|---|
| start→poll→GetQueryExecution (SELECT) + .csv artifact | PASS | a46f9bf4-9b1d-4005-986b-ca22669a3be9 SUCCEEDED DML/SELECT; OutputLocation=s3://nb03-529b6396a930/results/a46f9bf4-9b1d-4005-986b-ca22669a3be9.csv | 274 |
| GetQueryResults paginates (header on page 0, opaque NextToken) | PASS | 3 manual pages (3+2+1 rows); botocore paginator merged 6 rows losslessly |  |
| batch_get/list executions (unprocessed IDs, paged, newest first) | PASS | unknown id → UnprocessedQueryExecutionIds; MaxResults=1 paginated 2 executions newest-first |  |
| GetQueryRuntimeStatistics (Timeline + Rows shape) | PASS | EngineExecutionTimeInMillis=0 InputBytes=0 |  |
| GetQueryResults on a running execution → 400 | PASS | InvalidRequestException (400): Query has not yet finished. Current state: RUNNING |  |
| StopQueryExecution → CANCELLED | PASS | 4e03ff12-b4a6-43be-92e0-f60aef9852fe CANCELLED |  |
| stop on a terminal execution (AWS no-ops with 200) | PASS | 200 no-op on a SUCCEEDED execution |  |
| CREATE DATABASE → Glue database + .txt artifact (dialect map) | PASS | eff0bdb4-bcf9-40ba-8caa-b8ef4fa23319 SUCCEEDED DDL/CREATE_DATABASE; nb03_ddl_1c303e90 visible via glue.get_database; .txt + .txt.metadata written | 271 |
| CTAS → -manifest.csv + .metadata + Glue table (parquet at external_location) | PASS | 4c8be595-5475-4052-b3b3-55e84fc9763e SUCCEEDED DDL/CREATE_TABLE_AS_SELECT; manifest lists 1 file(s) under ctas-data/ | 263 |
| syntax error → submit-time InvalidRequestException 400 | PASS | InvalidRequestException (400); message starts 'Exception parsing query' |  |
| analysis error → FAILED execution with StateChangeReason | PASS | 1365693f-748d-450b-85c5-990b851c76ba FAILED: line 1:15: Table 'hive.nb03_1c303e90.no_such_table_xyz' does not exist |  |
| unknown QueryExecutionId → InvalidRequestException 400 | PASS | InvalidRequestException (400) |  |
| missing OutputLocation (primary, no ResultConfiguration) → 400 | PASS | InvalidRequestException (400) |  |
| EXECUTE + ExecutionParameters binds and echoes | PASS | nb03_stmt_1c303e90 → row 'hello'; ExecutionParameters echoed | 267 |
| qmark ExecutionParameters on a plain query | PASS | SELECT ? with ['42'] → row '42' | 266 |
| EXECUTE failures → FAILED not 400 (missing stmt, ?-count) | PASS | both FAILED with Athena's StateChangeReason phrasing |  |
| ClientRequestToken dedupes retried submissions | PASS | token 9b766d13… → single execution 36bd7408… |  |
| ResultReuseConfiguration reuses recent results | PASS | second identical run reused (ReusedPreviousResult=True) |  |
| ResultConfiguration.EncryptionConfiguration echoed verbatim | PASS | SSE_S3 + KmsKey echoed on GetQueryExecution | 266 |
| QueryExecutionContext.Catalog=AwsDataCatalog round-trips | PASS | 790d2a1b-98e0-49cc-bbdf-2f9708d8038e SUCCEEDED; catalog echoed | 264 |
| unknown catalog rejected at submit | GAP | nb03_nocat_1c303e90 accepted → SUCCEEDED on the hive catalog regardless; real AWS rejects unregistered catalogs |  |
