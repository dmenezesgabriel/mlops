## 03_boto3_query_lifecycle

| feature | status | detail | latency_ms |
|---|---|---|---|
| start→poll→GetQueryExecution (SELECT) + .csv artifact | PASS | 02df9059-2a29-481e-8da2-c8c160f1fb79 SUCCEEDED DML/SELECT; OutputLocation=s3://nb03-87a67d4aa234/results/02df9059-2a29-481e-8da2-c8c160f1fb79.csv | 299.765 |
| GetQueryResults paginates (header on page 0, opaque NextToken) | PASS | 3 manual pages (3+2+1 rows); botocore paginator merged 6 rows losslessly |  |
| batch_get/list executions (unprocessed IDs, paged, newest first) | PASS | unknown id → UnprocessedQueryExecutionIds; MaxResults=1 paginated 2 executions newest-first |  |
| GetQueryRuntimeStatistics (Timeline + Rows shape) | PASS | EngineExecutionTimeInMillis=8 InputBytes=0 |  |
| GetQueryResults on a running execution → 400 | PASS | InvalidRequestException (400): Query has not yet finished. Current state: RUNNING |  |
| StopQueryExecution → CANCELLED | PASS | f6f9e534-77c3-4de7-a08f-5d14478ae07e CANCELLED |  |
| stop on a terminal execution (AWS no-ops with 200) | PASS | 200 no-op on a SUCCEEDED execution |  |
| CREATE DATABASE → Glue database + .txt artifact (dialect map) | PASS | 9365591c-1891-42da-89ec-a419025d728e SUCCEEDED DDL/CREATE_DATABASE; nb03_ddl_44370db2 visible via glue.get_database; .txt + .txt.metadata written | 225.596 |
| CTAS → -manifest.csv + .metadata + Glue table (parquet at external_location) | PASS | 5367dc9b-4432-4d62-81d9-cd7f46d849dd SUCCEEDED DDL/CREATE_TABLE_AS_SELECT; manifest lists 1 file(s) under ctas-data/ | 607.416 |
| syntax error → submit-time InvalidRequestException 400 | PASS | InvalidRequestException (400); message starts 'Exception parsing query' |  |
| analysis error → FAILED execution with StateChangeReason | PASS | 98cd6ef2-757e-44cb-9e66-b57a67993c6d FAILED: line 1:15: Table 'hive.nb03_44370db2.no_such_table_xyz' does not exist |  |
| unknown QueryExecutionId → InvalidRequestException 400 | PASS | InvalidRequestException (400) |  |
| missing OutputLocation (primary, no ResultConfiguration) → 400 | PASS | InvalidRequestException (400) |  |
| EXECUTE + ExecutionParameters binds and echoes | PASS | nb03_stmt_44370db2 → row 'hello'; ExecutionParameters echoed | 292.848 |
| qmark ExecutionParameters on a plain query | PASS | SELECT ? with ['42'] → row '42' | 293.045 |
| EXECUTE failures → FAILED not 400 (missing stmt, ?-count) | PASS | both FAILED with Athena's StateChangeReason phrasing |  |
| ClientRequestToken dedupes retried submissions | PASS | token 3235050d… → single execution 24577e0e… |  |
| ResultReuseConfiguration reuses recent results | PASS | second identical run reused (ReusedPreviousResult=True) |  |
| ResultConfiguration.EncryptionConfiguration echoed verbatim | PASS | SSE_S3 + KmsKey echoed on GetQueryExecution | 304.794 |
| QueryExecutionContext.Catalog=AwsDataCatalog round-trips | PASS | 1dff195b-069f-420f-b416-cf627a360872 SUCCEEDED; catalog echoed | 311.084 |
| unknown catalog rejected at submit | PASS | InvalidRequestException (400) |  |
