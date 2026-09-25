## 03_boto3_query_lifecycle

| feature | status | detail | latency_ms |
|---|---|---|---|
| start→poll→GetQueryExecution (SELECT) + .csv artifact | PASS | 4eeced06-09b4-44a4-baf8-d6912123132d SUCCEEDED DML/SELECT; OutputLocation=s3://nb03-42f350e48b61/results/4eeced06-09b4-44a4-baf8-d6912123132d.csv | 272 |
| GetQueryResults paginates (header on page 0, opaque NextToken) | PASS | 3 manual pages (3+2+1 rows); botocore paginator merged 6 rows losslessly |  |
| batch_get/list executions (unprocessed IDs, paged, newest first) | PASS | unknown id → UnprocessedQueryExecutionIds; MaxResults=1 paginated 2 executions newest-first |  |
| GetQueryRuntimeStatistics (Timeline + Rows shape) | PASS | EngineExecutionTimeInMillis=0 InputBytes=0 |  |
| GetQueryResults on a running execution → 400 | PASS | InvalidRequestException (400): Query has not yet finished. Current state: RUNNING |  |
| StopQueryExecution → CANCELLED | PASS | 42ff6e30-ea87-496d-ba71-14da201771d8 CANCELLED |  |
| stop on a terminal execution (AWS no-ops with 200) | PASS | 200 no-op on a SUCCEEDED execution |  |
| CREATE DATABASE → Glue database + .txt artifact (dialect map) | PASS | 4c501bc2-5245-4288-9944-a8b1bdfc942f SUCCEEDED DDL/CREATE_DATABASE; nb03_ddl_334bdb10 visible via glue.get_database; .txt + .txt.metadata written | 268 |
| CTAS → -manifest.csv + .metadata + Glue table (parquet at external_location) | PASS | cc46b507-fa3d-44ea-a634-56732ffe4d0f SUCCEEDED DDL/CREATE_TABLE_AS_SELECT; manifest lists 1 file(s) under ctas-data/ | 264 |
| syntax error → submit-time InvalidRequestException 400 | PASS | InvalidRequestException (400); message starts 'Exception parsing query' |  |
| analysis error → FAILED execution with StateChangeReason | PASS | 5aceca5b-045b-47c7-a482-0eeb5b694cd7 FAILED: line 1:15: Table 'hive.nb03_334bdb10.no_such_table_xyz' does not exist |  |
| unknown QueryExecutionId → InvalidRequestException 400 | PASS | InvalidRequestException (400) |  |
| missing OutputLocation (primary, no ResultConfiguration) → 400 | PASS | InvalidRequestException (400) |  |
| EXECUTE + ExecutionParameters binds and echoes | PASS | nb03_stmt_334bdb10 → row 'hello'; ExecutionParameters echoed | 264 |
| qmark ExecutionParameters on a plain query | PASS | SELECT ? with ['42'] → row '42' | 262 |
| EXECUTE failures → FAILED not 400 (missing stmt, ?-count) | PASS | both FAILED with Athena's StateChangeReason phrasing |  |
| ClientRequestToken dedupes retried submissions | PASS | token aa2d0d51… → single execution 8c1ee029… |  |
| ResultReuseConfiguration reuses recent results | GAP | second identical run SUCCEEDED (ReusedPreviousResult=None, config echoed=False); AWS re-answers the recent result |  |
| ResultConfiguration.EncryptionConfiguration echoed verbatim | PASS | SSE_S3 + KmsKey echoed on GetQueryExecution | 267 |
| QueryExecutionContext.Catalog=AwsDataCatalog round-trips | PASS | 972e552b-1f85-4c6a-b737-9d06677abbcb SUCCEEDED; catalog echoed | 264 |
| unknown catalog rejected at submit | GAP | nb03_nocat_334bdb10 accepted → SUCCEEDED on the hive catalog regardless; real AWS rejects unregistered catalogs |  |
