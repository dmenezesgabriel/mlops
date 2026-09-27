## 03_boto3_query_lifecycle

| feature | status | detail | latency_ms |
|---|---|---|---|
| start→poll→GetQueryExecution (SELECT) + .csv artifact | PASS | 7de5bb6b-8fc2-4217-9c36-4bebc6d3d69c SUCCEEDED DML/SELECT; OutputLocation=s3://nb03-f7c6a16082e7/results/7de5bb6b-8fc2-4217-9c36-4bebc6d3d69c.csv | 289 |
| GetQueryResults paginates (header on page 0, opaque NextToken) | PASS | 3 manual pages (3+2+1 rows); botocore paginator merged 6 rows losslessly |  |
| batch_get/list executions (unprocessed IDs, paged, newest first) | PASS | unknown id → UnprocessedQueryExecutionIds; MaxResults=1 paginated 2 executions newest-first |  |
| GetQueryRuntimeStatistics (Timeline + Rows shape) | PASS | EngineExecutionTimeInMillis=0 InputBytes=0 |  |
| GetQueryResults on a running execution → 400 | PASS | InvalidRequestException (400): Query has not yet finished. Current state: RUNNING |  |
| StopQueryExecution → CANCELLED | PASS | f4894804-d6ea-4a8e-8460-692d8f92a97a CANCELLED |  |
| stop on a terminal execution (AWS no-ops with 200) | PASS | 200 no-op on a SUCCEEDED execution |  |
| CREATE DATABASE → Glue database + .txt artifact (dialect map) | PASS | 645e791a-8285-4ce9-b21f-4c51de224c88 SUCCEEDED DDL/CREATE_DATABASE; nb03_ddl_afff2f34 visible via glue.get_database; .txt + .txt.metadata written | 278 |
| CTAS → -manifest.csv + .metadata + Glue table (parquet at external_location) | PASS | 35d6ddc6-daf5-4ac1-9ff1-8a6942962136 SUCCEEDED DDL/CREATE_TABLE_AS_SELECT; manifest lists 1 file(s) under ctas-data/ | 279 |
| syntax error → submit-time InvalidRequestException 400 | PASS | InvalidRequestException (400); message starts 'Exception parsing query' |  |
| analysis error → FAILED execution with StateChangeReason | PASS | 5c4825bf-3281-457c-b1fc-925af574466d FAILED: line 1:15: Table 'hive.nb03_afff2f34.no_such_table_xyz' does not exist |  |
| unknown QueryExecutionId → InvalidRequestException 400 | PASS | InvalidRequestException (400) |  |
| missing OutputLocation (primary, no ResultConfiguration) → 400 | PASS | InvalidRequestException (400) |  |
| EXECUTE + ExecutionParameters binds and echoes | PASS | nb03_stmt_afff2f34 → row 'hello'; ExecutionParameters echoed | 295 |
| qmark ExecutionParameters on a plain query | PASS | SELECT ? with ['42'] → row '42' | 278 |
| EXECUTE failures → FAILED not 400 (missing stmt, ?-count) | PASS | both FAILED with Athena's StateChangeReason phrasing |  |
| ClientRequestToken dedupes retried submissions | PASS | token e3b6e18c… → single execution e44337f2… |  |
| ResultReuseConfiguration reuses recent results | PASS | second identical run reused (ReusedPreviousResult=True) |  |
| ResultConfiguration.EncryptionConfiguration echoed verbatim | PASS | SSE_S3 + KmsKey echoed on GetQueryExecution | 289 |
| QueryExecutionContext.Catalog=AwsDataCatalog round-trips | PASS | e0c54752-476f-4226-a4d0-44f54c3a0b1c SUCCEEDED; catalog echoed | 284 |
| unknown catalog rejected at submit | PASS | InvalidRequestException (400) |  |
