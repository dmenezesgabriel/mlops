## 04_app_integration

| feature | status | detail | latency_ms |
|---|---|---|---|
| start→poll→GetQueryExecution (SELECT) + .csv artifact | PASS | f1888038-1a08-4fef-a4fb-28136725b757 SUCCEEDED DML/SELECT; OutputLocation=s3://nb04-4cebdaa42680/results/f1888038-1a08-4fef-a4fb-28136725b757.csv | 280.499 |
| GetQueryResults paginates (header on page 0, opaque NextToken) | PASS | 3 manual pages (3+2+1 rows); botocore paginator merged 6 rows losslessly |  |
| batch_get/list executions (unprocessed IDs, paged, newest first) | PASS | unknown id → UnprocessedQueryExecutionIds; MaxResults=1 paginated 2 executions newest-first |  |
| GetQueryRuntimeStatistics (Timeline + Rows shape) | PASS | EngineExecutionTimeInMillis=2 InputBytes=0 |  |
| StopQueryExecution → CANCELLED | PASS | 6c8aacfb-74b9-422f-a171-5111724665d6 CANCELLED |  |
| stop on a terminal execution (AWS no-ops with 200) | PASS | 200 no-op on a SUCCEEDED execution |  |
| named queries create/get/list (MaxResults+NextToken pagination) | PASS | 2 queries in nb04-wg-16c36348, first-page token='1' |  |
| named queries batch_get unprocessed IDs + delete→400 | PASS | unprocessed=['00000000-0000-0000-0000-000000000000']; deleted get → InvalidRequestException |  |
| prepared statements create/get/update/list/batch_get | PASS | nb04_stmt_16c36348 in nb04-wg-16c36348; unprocessed names surfaced |  |
| prepared statements missing/deleted → ResourceNotFoundException 404 | PASS | missing get/update + deleted get → 404 |  |
| EXECUTE + ExecutionParameters binds and echoes | PASS | nb04_stmt_16c36348 → row 'hello'; ExecutionParameters echoed | 265.744 |
| qmark ExecutionParameters on a plain query | PASS | SELECT ? with ['42'] → row '42' | 268.719 |
| EXECUTE failures → FAILED not 400 (missing stmt, ?-count) | PASS | both FAILED with Athena's StateChangeReason phrasing |  |
| ClientRequestToken dedupes retried submissions | PASS | token f760ac59… → single execution e47698ca… |  |
| ResultReuseConfiguration reuses recent results | PASS | second identical run reused (ReusedPreviousResult=True) |  |
| ResultConfiguration.EncryptionConfiguration echoed verbatim | PASS | SSE_S3 + KmsKey echoed on GetQueryExecution | 266.086 |
| QueryExecutionContext.Catalog=AwsDataCatalog round-trips | PASS | d270b0ff-32cf-4525-93e5-bbe8b487e990 SUCCEEDED; catalog echoed | 267.139 |
