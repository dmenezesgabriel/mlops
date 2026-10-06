## 03_boto3_query_lifecycle

| feature | status | detail | latency_ms |
|---|---|---|---|
| start→poll→GetQueryExecution (SELECT) + .csv artifact | PASS | 1587cec9-d254-4818-a20b-9520f57277d1 SUCCEEDED DML/SELECT; OutputLocation=s3://nb03-cd691ace62ce/results/1587cec9-d254-4818-a20b-9520f57277d1.csv | 426.366 |
| GetQueryResults paginates (header on page 0, opaque NextToken) | PASS | 3 manual pages (3+2+1 rows); botocore paginator merged 6 rows losslessly |  |
| batch_get/list executions (unprocessed IDs, paged, newest first) | PASS | unknown id → UnprocessedQueryExecutionIds; MaxResults=1 paginated 2 executions newest-first |  |
| GetQueryRuntimeStatistics (Timeline + Rows shape) | PASS | EngineExecutionTimeInMillis=0 InputBytes=0 |  |
| GetQueryResults on a running execution → 400 | PASS | InvalidRequestException (400): Query has not yet finished. Current state: RUNNING |  |
| StopQueryExecution → CANCELLED | PASS | ed00b9f1-8da3-406f-bdcd-0a2627db7588 CANCELLED |  |
| stop on a terminal execution (AWS no-ops with 200) | PASS | 200 no-op on a SUCCEEDED execution |  |
| CREATE DATABASE → Glue database + .txt artifact (dialect map) | PASS | 4f59ecc1-742e-41b0-bbf5-013763365e16 SUCCEEDED DDL/CREATE_DATABASE; nb03_ddl_a541b8a4 visible via glue.get_database; .txt + .txt.metadata written | 281.196 |
| CTAS → -manifest.csv + .metadata + Glue table (parquet at external_location) | PASS | e1bc5b38-1fd4-42ff-8ff4-c815162da539 SUCCEEDED DDL/CREATE_TABLE_AS_SELECT; manifest lists 1 file(s) under ctas-data/ | 287.101 |
| syntax error → submit-time InvalidRequestException 400 | PASS | InvalidRequestException (400); message starts 'Exception parsing query' |  |
| analysis error → FAILED execution with StateChangeReason | PASS | 7df723c8-86e3-400f-98dd-be0b28767ed4 FAILED: line 1:15: Table 'hive.nb03_a541b8a4.no_such_table_xyz' does not exist |  |
| unknown QueryExecutionId → InvalidRequestException 400 | PASS | InvalidRequestException (400) |  |
| missing OutputLocation (primary, no ResultConfiguration) → 400 | PASS | InvalidRequestException (400) |  |
| EXECUTE + ExecutionParameters binds and echoes | PASS | nb03_stmt_a541b8a4 → row 'hello'; ExecutionParameters echoed | 295.341 |
| qmark ExecutionParameters on a plain query | PASS | SELECT ? with ['42'] → row '42' | 293.845 |
| EXECUTE failures → FAILED not 400 (missing stmt, ?-count) | PASS | both FAILED with Athena's StateChangeReason phrasing |  |
| ClientRequestToken dedupes retried submissions | PASS | token e7e6a8e8… → single execution 32025448… |  |
| ResultReuseConfiguration reuses recent results | PASS | second identical run reused (ReusedPreviousResult=True) |  |
| ResultConfiguration.EncryptionConfiguration echoed verbatim | PASS | SSE_S3 + KmsKey echoed on GetQueryExecution | 293.826 |
| QueryExecutionContext.Catalog=AwsDataCatalog round-trips | PASS | b3594648-d9f6-489b-a0b9-a9b3147bce60 SUCCEEDED; catalog echoed | 294.811 |
| unknown catalog rejected at submit | PASS | InvalidRequestException (400) |  |
