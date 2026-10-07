## 03_boto3_query_lifecycle

| feature | status | detail | latency_ms |
|---|---|---|---|
| start→poll→GetQueryExecution (SELECT) + .csv artifact | PASS | 88f8d443-979a-4730-a55b-55a3f4b1e76d SUCCEEDED DML/SELECT; OutputLocation=s3://nb03-efdc7504cdf8/results/88f8d443-979a-4730-a55b-55a3f4b1e76d.csv | 302.777 |
| GetQueryResults paginates (header on page 0, opaque NextToken) | PASS | 3 manual pages (3+2+1 rows); botocore paginator merged 6 rows losslessly |  |
| batch_get/list executions (unprocessed IDs, paged, newest first) | PASS | unknown id → UnprocessedQueryExecutionIds; MaxResults=1 paginated 2 executions newest-first |  |
| GetQueryRuntimeStatistics (Timeline + Rows shape) | PASS | EngineExecutionTimeInMillis=1 InputBytes=0 |  |
| GetQueryResults on a running execution → 400 | PASS | InvalidRequestException (400): Query has not yet finished. Current state: RUNNING |  |
| StopQueryExecution → CANCELLED | PASS | 3197c6f4-7d8b-4dc0-b74b-650735719271 CANCELLED |  |
| stop on a terminal execution (AWS no-ops with 200) | PASS | 200 no-op on a SUCCEEDED execution |  |
| CREATE DATABASE → Glue database + .txt artifact (dialect map) | PASS | 99f0d939-0e96-4bbc-88f7-94c1ef86f3c9 SUCCEEDED DDL/CREATE_DATABASE; nb03_ddl_1a6f99ed visible via glue.get_database; .txt + .txt.metadata written | 290.199 |
| CTAS → -manifest.csv + .metadata + Glue table (parquet at external_location) | PASS | f0d3a76d-17da-400e-80b5-76546d9c124e SUCCEEDED DDL/CREATE_TABLE_AS_SELECT; manifest lists 1 file(s) under ctas-data/ | 341.901 |
| syntax error → submit-time InvalidRequestException 400 | PASS | InvalidRequestException (400); message starts 'Exception parsing query' |  |
| analysis error → FAILED execution with StateChangeReason | PASS | 3a74cd98-7a0f-4ab7-af85-5fea9c89a414 FAILED: line 1:15: Table 'hive.nb03_1a6f99ed.no_such_table_xyz' does not exist |  |
| unknown QueryExecutionId → InvalidRequestException 400 | PASS | InvalidRequestException (400) |  |
| missing OutputLocation (primary, no ResultConfiguration) → 400 | PASS | InvalidRequestException (400) |  |
| EXECUTE + ExecutionParameters binds and echoes | PASS | nb03_stmt_1a6f99ed → row 'hello'; ExecutionParameters echoed | 293.503 |
| qmark ExecutionParameters on a plain query | PASS | SELECT ? with ['42'] → row '42' | 310.47 |
| EXECUTE failures → FAILED not 400 (missing stmt, ?-count) | PASS | both FAILED with Athena's StateChangeReason phrasing |  |
| ClientRequestToken dedupes retried submissions | PASS | token 05e5c927… → single execution ff29ffdb… |  |
| ResultReuseConfiguration reuses recent results | PASS | second identical run reused (ReusedPreviousResult=True) |  |
| ResultConfiguration.EncryptionConfiguration echoed verbatim | PASS | SSE_S3 + KmsKey echoed on GetQueryExecution | 292.564 |
| QueryExecutionContext.Catalog=AwsDataCatalog round-trips | PASS | 08dfae93-e127-4b44-a2c8-6f4525dc0284 SUCCEEDED; catalog echoed | 294.694 |
| unknown catalog rejected at submit | PASS | InvalidRequestException (400) |  |
