## 04_app_integration

| feature | status | detail | latency_ms |
|---|---|---|---|
| start→poll→GetQueryExecution (SELECT) + .csv artifact | PASS | 35fa0a22-a88b-4eae-8359-75f026a1efc4 SUCCEEDED DML/SELECT; OutputLocation=s3://nb04-4482b0ab9d54/results/35fa0a22-a88b-4eae-8359-75f026a1efc4.csv | 266.066 |
| GetQueryResults paginates (header on page 0, opaque NextToken) | PASS | 3 manual pages (3+2+1 rows); botocore paginator merged 6 rows losslessly |  |
| batch_get/list executions (unprocessed IDs, paged, newest first) | PASS | unknown id → UnprocessedQueryExecutionIds; MaxResults=1 paginated 2 executions newest-first |  |
| GetQueryRuntimeStatistics (Timeline + Rows shape) | PASS | EngineExecutionTimeInMillis=0 InputBytes=0 |  |
| StopQueryExecution → CANCELLED | PASS | 3259eade-649e-424c-9da1-119b74556764 CANCELLED |  |
| stop on a terminal execution (AWS no-ops with 200) | PASS | 200 no-op on a SUCCEEDED execution |  |
| named queries create/get/list (MaxResults+NextToken pagination) | PASS | 2 queries in nb04-wg-14851a3a, first-page token='1' |  |
| named queries batch_get unprocessed IDs + delete→400 | PASS | unprocessed=['00000000-0000-0000-0000-000000000000']; deleted get → InvalidRequestException |  |
| prepared statements create/get/update/list/batch_get | PASS | nb04_stmt_14851a3a in nb04-wg-14851a3a; unprocessed names surfaced |  |
| prepared statements missing/deleted → ResourceNotFoundException 404 | PASS | missing get/update + deleted get → 404 |  |
| EXECUTE + ExecutionParameters binds and echoes | PASS | nb04_stmt_14851a3a → row 'hello'; ExecutionParameters echoed | 263.333 |
| qmark ExecutionParameters on a plain query | PASS | SELECT ? with ['42'] → row '42' | 267.535 |
| EXECUTE failures → FAILED not 400 (missing stmt, ?-count) | PASS | both FAILED with Athena's StateChangeReason phrasing |  |
| ClientRequestToken dedupes retried submissions | PASS | token 4c924080… → single execution 8d059db9… |  |
| ResultReuseConfiguration reuses recent results | PASS | second identical run reused (ReusedPreviousResult=True) |  |
| ResultConfiguration.EncryptionConfiguration echoed verbatim | PASS | SSE_S3 + KmsKey echoed on GetQueryExecution | 269.743 |
| QueryExecutionContext.Catalog=AwsDataCatalog round-trips | PASS | 8552c07d-dc20-4bd4-b291-3ed979458dac SUCCEEDED; catalog echoed | 270.909 |
