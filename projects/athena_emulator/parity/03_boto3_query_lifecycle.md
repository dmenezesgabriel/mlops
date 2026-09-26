## 03_boto3_query_lifecycle

| feature | status | detail | latency_ms |
|---|---|---|---|
| start→poll→GetQueryExecution (SELECT) + .csv artifact | PASS | 82faadb8-c57f-4eb6-8309-201038728e9a SUCCEEDED DML/SELECT; OutputLocation=s3://nb03-0d86b3cba94f/results/82faadb8-c57f-4eb6-8309-201038728e9a.csv | 274 |
| GetQueryResults paginates (header on page 0, opaque NextToken) | PASS | 3 manual pages (3+2+1 rows); botocore paginator merged 6 rows losslessly |  |
| batch_get/list executions (unprocessed IDs, paged, newest first) | PASS | unknown id → UnprocessedQueryExecutionIds; MaxResults=1 paginated 2 executions newest-first |  |
| GetQueryRuntimeStatistics (Timeline + Rows shape) | PASS | EngineExecutionTimeInMillis=0 InputBytes=0 |  |
| GetQueryResults on a running execution → 400 | PASS | InvalidRequestException (400): Query has not yet finished. Current state: RUNNING |  |
| StopQueryExecution → CANCELLED | PASS | c9fdb8c6-1050-42e1-b67b-df319ff67dc9 CANCELLED |  |
| stop on a terminal execution (AWS no-ops with 200) | PASS | 200 no-op on a SUCCEEDED execution |  |
| CREATE DATABASE → Glue database + .txt artifact (dialect map) | PASS | 3a9b8e85-a0a5-4434-972c-9fd263202256 SUCCEEDED DDL/CREATE_DATABASE; nb03_ddl_0e9fa441 visible via glue.get_database; .txt + .txt.metadata written | 267 |
| CTAS → -manifest.csv + .metadata + Glue table (parquet at external_location) | PASS | fa28dd18-e45a-48a7-bd40-da58493d631c SUCCEEDED DDL/CREATE_TABLE_AS_SELECT; manifest lists 1 file(s) under ctas-data/ | 265 |
| syntax error → submit-time InvalidRequestException 400 | PASS | InvalidRequestException (400); message starts 'Exception parsing query' |  |
| analysis error → FAILED execution with StateChangeReason | PASS | 8311ebe0-9123-4f6b-9466-e65d84e1dc8b FAILED: line 1:15: Table 'hive.nb03_0e9fa441.no_such_table_xyz' does not exist |  |
| unknown QueryExecutionId → InvalidRequestException 400 | PASS | InvalidRequestException (400) |  |
| missing OutputLocation (primary, no ResultConfiguration) → 400 | PASS | InvalidRequestException (400) |  |
| EXECUTE + ExecutionParameters binds and echoes | PASS | nb03_stmt_0e9fa441 → row 'hello'; ExecutionParameters echoed | 266 |
| qmark ExecutionParameters on a plain query | PASS | SELECT ? with ['42'] → row '42' | 264 |
| EXECUTE failures → FAILED not 400 (missing stmt, ?-count) | PASS | both FAILED with Athena's StateChangeReason phrasing |  |
| ClientRequestToken dedupes retried submissions | PASS | token 88205eec… → single execution 64506787… |  |
| ResultReuseConfiguration reuses recent results | PASS | second identical run reused (ReusedPreviousResult=True) |  |
| ResultConfiguration.EncryptionConfiguration echoed verbatim | PASS | SSE_S3 + KmsKey echoed on GetQueryExecution | 265 |
| QueryExecutionContext.Catalog=AwsDataCatalog round-trips | PASS | 40b8e1ae-31fd-456d-8aa7-7285b28b6b54 SUCCEEDED; catalog echoed | 266 |
| unknown catalog rejected at submit | PASS | InvalidRequestException (400) |  |
