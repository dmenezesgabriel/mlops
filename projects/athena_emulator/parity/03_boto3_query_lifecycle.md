## 03_boto3_query_lifecycle

| feature | status | detail | latency_ms |
|---|---|---|---|
| start→poll→GetQueryExecution (SELECT) + .csv artifact | PASS | 92d55cc1-c8fb-4bb0-b431-db3bf4cddb82 SUCCEEDED DML/SELECT; OutputLocation=s3://nb03-3216e3a14ca8/results/92d55cc1-c8fb-4bb0-b431-db3bf4cddb82.csv | 82.027 |
| GetQueryResults paginates (header on page 0, opaque NextToken) | PASS | 3 manual pages (3+2+1 rows); botocore paginator merged 6 rows losslessly |  |
| batch_get/list executions (unprocessed IDs, paged, newest first) | PASS | unknown id → UnprocessedQueryExecutionIds; MaxResults=1 paginated 2 executions newest-first |  |
| GetQueryRuntimeStatistics (Timeline + Rows shape) | PASS | EngineExecutionTimeInMillis=0 InputBytes=0 |  |
| GetQueryResults on a running execution → 400 | PASS | InvalidRequestException (400): Query has not yet finished. Current state: RUNNING |  |
| StopQueryExecution → CANCELLED | PASS | 81e8ab9e-352e-4932-a37b-d9f964af6240 CANCELLED |  |
| stop on a terminal execution (AWS no-ops with 200) | PASS | 200 no-op on a SUCCEEDED execution |  |
| CREATE DATABASE → Glue database + .txt artifact (dialect map) | PASS | 83eea215-f53f-497c-af1c-542c63cbcce5 SUCCEEDED DDL/CREATE_DATABASE; nb03_ddl_4815a2e6 visible via glue.get_database; .txt + .txt.metadata written | 295.045 |
| CTAS → -manifest.csv + .metadata + Glue table (parquet at external_location) | PASS | 8f0c9161-dba7-4c92-8946-aac50af4b277 SUCCEEDED DDL/CREATE_TABLE_AS_SELECT; manifest lists 1 file(s) under ctas-data/ | 313.477 |
| syntax error → submit-time InvalidRequestException 400 | PASS | InvalidRequestException (400); message starts 'Exception parsing query' |  |
| analysis error → FAILED execution with StateChangeReason | PASS | f236dc49-5e27-4c6d-a1b1-1a49991a8372 FAILED: line 1:15: Table 'hive.nb03_4815a2e6.no_such_table_xyz' does not exist |  |
| unknown QueryExecutionId → InvalidRequestException 400 | PASS | InvalidRequestException (400) |  |
| missing OutputLocation (primary, no ResultConfiguration) → 400 | PASS | InvalidRequestException (400) |  |
| EXECUTE + ExecutionParameters binds and echoes | PASS | nb03_stmt_4815a2e6 → row 'hello'; ExecutionParameters echoed | 303.734 |
| qmark ExecutionParameters on a plain query | PASS | SELECT ? with ['42'] → row '42' | 281.846 |
| EXECUTE failures → FAILED not 400 (missing stmt, ?-count) | PASS | both FAILED with Athena's StateChangeReason phrasing |  |
| ClientRequestToken dedupes retried submissions | PASS | token 51eccea1… → single execution 4e4adebc… |  |
| ResultReuseConfiguration reuses recent results | PASS | second identical run reused (ReusedPreviousResult=True) |  |
| ResultConfiguration.EncryptionConfiguration echoed verbatim | PASS | SSE_S3 + KmsKey echoed on GetQueryExecution | 317.595 |
| QueryExecutionContext.Catalog=AwsDataCatalog round-trips | PASS | 797285aa-858a-43c4-9e89-76a61ba2f1aa SUCCEEDED; catalog echoed | 313.171 |
| unknown catalog rejected at submit | PASS | InvalidRequestException (400) |  |
