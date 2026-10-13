## 04_app_integration

| feature | status | detail | latency_ms |
|---|---|---|---|
| start→poll→GetQueryExecution (SELECT) + .csv artifact | PASS | 1844c11e-f0d6-4ae2-9655-f2a49cd0cfd8 SUCCEEDED DML/SELECT; OutputLocation=s3://nb04-4322e7e1a5e2/results/1844c11e-f0d6-4ae2-9655-f2a49cd0cfd8.csv | 293.149 |
| GetQueryResults paginates (header on page 0, opaque NextToken) | PASS | 3 manual pages (3+2+1 rows); botocore paginator merged 6 rows losslessly |  |
| batch_get/list executions (unprocessed IDs, paged, newest first) | PASS | unknown id → UnprocessedQueryExecutionIds; MaxResults=1 paginated 2 executions newest-first |  |
| GetQueryRuntimeStatistics (Timeline + Rows shape) | PASS | EngineExecutionTimeInMillis=1 InputBytes=0 |  |
| StopQueryExecution → CANCELLED | PASS | 40a5d767-ba89-4f04-bbaa-05159d709be9 CANCELLED |  |
| stop on a terminal execution (AWS no-ops with 200) | PASS | 200 no-op on a SUCCEEDED execution |  |
| named queries create/get/list (MaxResults+NextToken pagination) | PASS | 2 queries in nb04-wg-5c7bf041, first-page token='1' |  |
| named queries batch_get unprocessed IDs + delete→400 | PASS | unprocessed=['00000000-0000-0000-0000-000000000000']; deleted get → InvalidRequestException |  |
| prepared statements create/get/update/list/batch_get | PASS | nb04_stmt_5c7bf041 in nb04-wg-5c7bf041; unprocessed names surfaced |  |
| prepared statements missing/deleted → ResourceNotFoundException 404 | PASS | missing get/update + deleted get → 404 |  |
| EXECUTE + ExecutionParameters binds and echoes | PASS | nb04_stmt_5c7bf041 → row 'hello'; ExecutionParameters echoed | 306.842 |
| qmark ExecutionParameters on a plain query | PASS | SELECT ? with ['42'] → row '42' | 275.04 |
| EXECUTE failures → FAILED not 400 (missing stmt, ?-count) | PASS | both FAILED with Athena's StateChangeReason phrasing |  |
| ClientRequestToken dedupes retried submissions | PASS | token 6dbccf66… → single execution a6898059… |  |
| ResultReuseConfiguration reuses recent results | PASS | second identical run reused (ReusedPreviousResult=True) |  |
| ResultConfiguration.EncryptionConfiguration echoed verbatim | PASS | SSE_S3 + KmsKey echoed on GetQueryExecution | 292.253 |
| QueryExecutionContext.Catalog=AwsDataCatalog round-trips | PASS | 7621a1bd-3842-42e2-82c8-a9916c404385 SUCCEEDED; catalog echoed | 293.833 |
