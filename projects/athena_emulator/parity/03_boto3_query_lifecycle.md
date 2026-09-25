## 03_boto3_query_lifecycle

| feature | status | detail | latency_ms |
|---|---|---|---|
| start→poll→GetQueryExecution (SELECT) + .csv artifact | PASS | 822abcf2-99cd-40f6-a94f-40b6460d5932 SUCCEEDED DML/SELECT; OutputLocation=s3://nb03-c79fd0039fa7/results/822abcf2-99cd-40f6-a94f-40b6460d5932.csv | 320 |
| GetQueryResults paginates (header on page 0, opaque NextToken) | PASS | 3 manual pages (3+2+1 rows); botocore paginator merged 6 rows losslessly |  |
| batch_get/list executions (unprocessed IDs, paged, newest first) | PASS | unknown id → UnprocessedQueryExecutionIds; MaxResults=1 paginated 2 executions newest-first |  |
| GetQueryRuntimeStatistics (Timeline + Rows shape) | PASS | EngineExecutionTimeInMillis=0 InputBytes=0 |  |
| GetQueryResults on a running execution → 400 | PASS | InvalidRequestException (400): Query has not yet finished. Current state: RUNNING |  |
| StopQueryExecution → CANCELLED | PASS | 0b669a86-e520-4dea-8502-13bdf41f93e3 CANCELLED |  |
| stop on a terminal execution (AWS no-ops with 200) | PASS | 200 no-op on a SUCCEEDED execution |  |
| CREATE DATABASE → Glue database + .txt artifact (dialect map) | PASS | f32d3330-3d71-4453-af08-7fcb3504b164 SUCCEEDED DDL/CREATE_DATABASE; nb03_ddl_05883043 visible via glue.get_database; .txt + .txt.metadata written | 293 |
| CTAS → -manifest.csv + .metadata + Glue table (parquet at external_location) | PASS | 512ef939-d9cc-4cb0-9659-5ffcfa3a6418 SUCCEEDED DDL/CREATE_TABLE_AS_SELECT; manifest lists 1 file(s) under ctas-data/ | 319 |
| syntax error → submit-time InvalidRequestException 400 | PASS | InvalidRequestException (400); message starts 'Exception parsing query' |  |
| analysis error → FAILED execution with StateChangeReason | PASS | aa143c9d-0462-4233-9350-bfcba8d289fe FAILED: line 1:15: Table 'hive.nb03_05883043.no_such_table_xyz' does not exist |  |
| unknown QueryExecutionId → InvalidRequestException 400 | PASS | InvalidRequestException (400) |  |
| missing OutputLocation (primary, no ResultConfiguration) → 400 | PASS | InvalidRequestException (400) |  |
| EXECUTE + ExecutionParameters binds and echoes | PASS | nb03_stmt_05883043 → row 'hello'; ExecutionParameters echoed | 300 |
| qmark ExecutionParameters on a plain query | PASS | SELECT ? with ['42'] → row '42' | 300 |
| EXECUTE failures → FAILED not 400 (missing stmt, ?-count) | PASS | both FAILED with Athena's StateChangeReason phrasing |  |
| ClientRequestToken dedupes retried submissions | GAP | token a4d39079… submitted twice → distinct executions 91b11d83…/626b3585…; AWS returns the original for a retried token |  |
| ResultReuseConfiguration reuses recent results | GAP | second identical run SUCCEEDED (ReusedPreviousResult=None, config echoed=False); AWS re-answers the recent result |  |
| ResultConfiguration.EncryptionConfiguration echoed verbatim | PASS | SSE_S3 + KmsKey echoed on GetQueryExecution | 292 |
| QueryExecutionContext.Catalog=AwsDataCatalog round-trips | PASS | 857b14e6-da9b-4106-bea2-fa589c096963 SUCCEEDED; catalog echoed | 321 |
| unknown catalog rejected at submit | GAP | nb03_nocat_05883043 accepted → SUCCEEDED on the hive catalog regardless; real AWS rejects unregistered catalogs |  |
