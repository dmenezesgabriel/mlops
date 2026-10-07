## 03_boto3_query_lifecycle

| feature | status | detail | latency_ms |
|---|---|---|---|
| start→poll→GetQueryExecution (SELECT) + .csv artifact | PASS | aa662bd3-86ee-40a6-a15c-262eef5cd2a5 SUCCEEDED DML/SELECT; OutputLocation=s3://nb03-4c118ae7ebde/results/aa662bd3-86ee-40a6-a15c-262eef5cd2a5.csv | 280.135 |
| GetQueryResults paginates (header on page 0, opaque NextToken) | PASS | 3 manual pages (3+2+1 rows); botocore paginator merged 6 rows losslessly |  |
| batch_get/list executions (unprocessed IDs, paged, newest first) | PASS | unknown id → UnprocessedQueryExecutionIds; MaxResults=1 paginated 2 executions newest-first |  |
| GetQueryRuntimeStatistics (Timeline + Rows shape) | PASS | EngineExecutionTimeInMillis=0 InputBytes=0 |  |
| GetQueryResults on a running execution → 400 | PASS | InvalidRequestException (400): Query has not yet finished. Current state: RUNNING |  |
| StopQueryExecution → CANCELLED | PASS | c15c50fa-a4c0-46a9-8a9d-f2507d89a09a CANCELLED |  |
| stop on a terminal execution (AWS no-ops with 200) | PASS | 200 no-op on a SUCCEEDED execution |  |
| CREATE DATABASE → Glue database + .txt artifact (dialect map) | PASS | 43f68e2d-48f8-4582-b5a2-ca1e666e34c8 SUCCEEDED DDL/CREATE_DATABASE; nb03_ddl_77af7f04 visible via glue.get_database; .txt + .txt.metadata written | 286.91 |
| CTAS → -manifest.csv + .metadata + Glue table (parquet at external_location) | PASS | 84ba8363-f155-4f9b-a719-0e2c100a93ff SUCCEEDED DDL/CREATE_TABLE_AS_SELECT; manifest lists 1 file(s) under ctas-data/ | 270.931 |
| syntax error → submit-time InvalidRequestException 400 | PASS | InvalidRequestException (400); message starts 'Exception parsing query' |  |
| analysis error → FAILED execution with StateChangeReason | PASS | 110dbbb6-6258-4b7a-959d-80cb83bfccd0 FAILED: line 1:15: Table 'hive.nb03_77af7f04.no_such_table_xyz' does not exist |  |
| unknown QueryExecutionId → InvalidRequestException 400 | PASS | InvalidRequestException (400) |  |
| missing OutputLocation (primary, no ResultConfiguration) → 400 | PASS | InvalidRequestException (400) |  |
| EXECUTE + ExecutionParameters binds and echoes | PASS | nb03_stmt_77af7f04 → row 'hello'; ExecutionParameters echoed | 277.722 |
| qmark ExecutionParameters on a plain query | PASS | SELECT ? with ['42'] → row '42' | 283.078 |
| EXECUTE failures → FAILED not 400 (missing stmt, ?-count) | PASS | both FAILED with Athena's StateChangeReason phrasing |  |
| ClientRequestToken dedupes retried submissions | PASS | token 75460c8b… → single execution f1c1d63a… |  |
| ResultReuseConfiguration reuses recent results | PASS | second identical run reused (ReusedPreviousResult=True) |  |
| ResultConfiguration.EncryptionConfiguration echoed verbatim | PASS | SSE_S3 + KmsKey echoed on GetQueryExecution | 279.556 |
| QueryExecutionContext.Catalog=AwsDataCatalog round-trips | PASS | 4c5e8c6e-26f2-4bfe-8a2e-6834534acec5 SUCCEEDED; catalog echoed | 272.688 |
| unknown catalog rejected at submit | PASS | InvalidRequestException (400) |  |
