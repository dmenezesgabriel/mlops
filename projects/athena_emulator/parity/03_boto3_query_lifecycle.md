## 03_boto3_query_lifecycle

| feature | status | detail | latency_ms |
|---|---|---|---|
| start→poll→GetQueryExecution (SELECT) + .csv artifact | PASS | cd43d9d2-4fa8-419a-802f-28f74957808e SUCCEEDED DML/SELECT; OutputLocation=s3://nb03-518197cc6afc/results/cd43d9d2-4fa8-419a-802f-28f74957808e.csv | 267 |
| GetQueryResults paginates (header on page 0, opaque NextToken) | PASS | 3 manual pages (3+2+1 rows); botocore paginator merged 6 rows losslessly |  |
| batch_get/list executions (unprocessed IDs, paged, newest first) | PASS | unknown id → UnprocessedQueryExecutionIds; MaxResults=1 paginated 2 executions newest-first |  |
| GetQueryRuntimeStatistics (Timeline + Rows shape) | PASS | EngineExecutionTimeInMillis=0 InputBytes=0 |  |
| GetQueryResults on a running execution → 400 | PASS | InvalidRequestException (400): Query has not yet finished. Current state: RUNNING |  |
| StopQueryExecution → CANCELLED | PASS | 53c63f3c-52cd-4032-a410-84115635cf79 CANCELLED |  |
| stop on a terminal execution (AWS no-ops with 200) | FAIL | InternalServerException (500) on a SUCCEEDED execution; real AWS answers a 200 no-op |  |
| CREATE DATABASE → Glue database + .txt artifact (dialect map) | PASS | f3d39908-54e4-4ec5-b319-01813cc663d8 SUCCEEDED DDL/CREATE_DATABASE; nb03_ddl_aae34d15 visible via glue.get_database; .txt + .txt.metadata written | 264 |
| CTAS → -manifest.csv + .metadata + Glue table (parquet at external_location) | PASS | 615812b6-ada6-4bd9-8512-42b967e0425d SUCCEEDED DDL/CREATE_TABLE_AS_SELECT; manifest lists 1 file(s) under ctas-data/ | 263 |
| syntax error → submit-time InvalidRequestException 400 | PASS | InvalidRequestException (400); message starts 'Exception parsing query' |  |
| analysis error → FAILED execution with StateChangeReason | PASS | aab3041d-c5bc-4f20-9a8b-8ac31d010187 FAILED: line 1:15: Table 'hive.nb03_aae34d15.no_such_table_xyz' does not exist |  |
| unknown QueryExecutionId → InvalidRequestException 400 | PASS | InvalidRequestException (400) |  |
| missing OutputLocation (primary, no ResultConfiguration) → 400 | PASS | InvalidRequestException (400) |  |
| EXECUTE + ExecutionParameters binds and echoes | PASS | nb03_stmt_aae34d15 → row 'hello'; ExecutionParameters echoed | 269 |
| qmark ExecutionParameters on a plain query | PASS | SELECT ? with ['42'] → row '42' | 267 |
| EXECUTE failures → FAILED not 400 (missing stmt, ?-count) | PASS | both FAILED with Athena's StateChangeReason phrasing |  |
| ClientRequestToken dedupes retried submissions | GAP | token 02a5e0a0… submitted twice → distinct executions 6605a571…/582d6d5e…; AWS returns the original for a retried token |  |
| ResultReuseConfiguration reuses recent results | GAP | second identical run SUCCEEDED (ReusedPreviousResult=None, config echoed=False); AWS re-answers the recent result |  |
| ResultConfiguration.EncryptionConfiguration echoed verbatim | PASS | SSE_S3 + KmsKey echoed on GetQueryExecution | 264 |
| QueryExecutionContext.Catalog=AwsDataCatalog round-trips | PASS | 5ec05f31-f6c2-4ab4-be62-3c1a7420f7d5 SUCCEEDED; catalog echoed | 264 |
| unknown catalog rejected at submit | GAP | nb03_nocat_aae34d15 accepted → SUCCEEDED on the hive catalog regardless; real AWS rejects unregistered catalogs |  |
