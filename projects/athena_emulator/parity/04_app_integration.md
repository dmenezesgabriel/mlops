## 04_app_integration

| feature | status | detail | latency_ms |
|---|---|---|---|
| start→poll→GetQueryExecution (SELECT) + .csv artifact | PASS | 436107ed-1e31-4722-8e6f-319bafc12e4b SUCCEEDED DML/SELECT; OutputLocation=s3://nb04-2025a34e62b9/results/436107ed-1e31-4722-8e6f-319bafc12e4b.csv | 265.619 |
| GetQueryResults paginates (header on page 0, opaque NextToken) | PASS | 3 manual pages (3+2+1 rows); botocore paginator merged 6 rows losslessly |  |
| batch_get/list executions (unprocessed IDs, paged, newest first) | PASS | unknown id → UnprocessedQueryExecutionIds; MaxResults=1 paginated 2 executions newest-first |  |
| GetQueryRuntimeStatistics (Timeline + Rows shape) | PASS | EngineExecutionTimeInMillis=0 InputBytes=0 |  |
| StopQueryExecution → CANCELLED | PASS | 81ecc079-4047-4ebc-939c-28040ae916a9 CANCELLED |  |
| stop on a terminal execution (AWS no-ops with 200) | PASS | 200 no-op on a SUCCEEDED execution |  |
| named queries create/get/list (MaxResults+NextToken pagination) | PASS | 2 queries in nb04-wg-1b794fe3, first-page token='1' |  |
| named queries batch_get unprocessed IDs + delete→400 | PASS | unprocessed=['00000000-0000-0000-0000-000000000000']; deleted get → InvalidRequestException |  |
| prepared statements create/get/update/list/batch_get | PASS | nb04_stmt_1b794fe3 in nb04-wg-1b794fe3; unprocessed names surfaced |  |
| prepared statements missing/deleted → ResourceNotFoundException 404 | PASS | missing get/update + deleted get → 404 |  |
| EXECUTE + ExecutionParameters binds and echoes | PASS | nb04_stmt_1b794fe3 → row 'hello'; ExecutionParameters echoed | 264.303 |
| qmark ExecutionParameters on a plain query | PASS | SELECT ? with ['42'] → row '42' | 264.578 |
| EXECUTE failures → FAILED not 400 (missing stmt, ?-count) | PASS | both FAILED with Athena's StateChangeReason phrasing |  |
| ClientRequestToken dedupes retried submissions | PASS | token 5b67d707… → single execution 32b90502… |  |
| ResultReuseConfiguration reuses recent results | PASS | second identical run reused (ReusedPreviousResult=True) |  |
| ResultConfiguration.EncryptionConfiguration echoed verbatim | PASS | SSE_S3 + KmsKey echoed on GetQueryExecution | 264.65 |
| QueryExecutionContext.Catalog=AwsDataCatalog round-trips | PASS | 0698ac6d-84f2-49c5-b71d-71e612e695c7 SUCCEEDED; catalog echoed | 274.329 |
