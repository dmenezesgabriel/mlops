## 04_app_integration

| feature | status | detail | latency_ms |
|---|---|---|---|
| start→poll→GetQueryExecution (SELECT) + .csv artifact | PASS | 1ab1547d-40be-41ab-a4d9-1272f853896f SUCCEEDED DML/SELECT; OutputLocation=s3://nb04-2c7405b9664f/results/1ab1547d-40be-41ab-a4d9-1272f853896f.csv | 295.655 |
| GetQueryResults paginates (header on page 0, opaque NextToken) | PASS | 3 manual pages (3+2+1 rows); botocore paginator merged 6 rows losslessly |  |
| batch_get/list executions (unprocessed IDs, paged, newest first) | PASS | unknown id → UnprocessedQueryExecutionIds; MaxResults=1 paginated 2 executions newest-first |  |
| GetQueryRuntimeStatistics (Timeline + Rows shape) | PASS | EngineExecutionTimeInMillis=2 InputBytes=0 |  |
| StopQueryExecution → CANCELLED | PASS | 1554a1ad-a297-4e4b-97fe-d47457917bb4 CANCELLED |  |
| stop on a terminal execution (AWS no-ops with 200) | PASS | 200 no-op on a SUCCEEDED execution |  |
| named queries create/get/list (MaxResults+NextToken pagination) | PASS | 2 queries in nb04-wg-b80760c9, first-page token='1' |  |
| named queries batch_get unprocessed IDs + delete→400 | PASS | unprocessed=['00000000-0000-0000-0000-000000000000']; deleted get → InvalidRequestException |  |
| prepared statements create/get/update/list/batch_get | PASS | nb04_stmt_b80760c9 in nb04-wg-b80760c9; unprocessed names surfaced |  |
| prepared statements missing/deleted → ResourceNotFoundException 404 | PASS | missing get/update + deleted get → 404 |  |
| EXECUTE + ExecutionParameters binds and echoes | PASS | nb04_stmt_b80760c9 → row 'hello'; ExecutionParameters echoed | 342.524 |
| qmark ExecutionParameters on a plain query | PASS | SELECT ? with ['42'] → row '42' | 278.087 |
| EXECUTE failures → FAILED not 400 (missing stmt, ?-count) | PASS | both FAILED with Athena's StateChangeReason phrasing |  |
| ClientRequestToken dedupes retried submissions | PASS | token d9091537… → single execution 58f5f66d… |  |
| ResultReuseConfiguration reuses recent results | PASS | second identical run reused (ReusedPreviousResult=True) |  |
| ResultConfiguration.EncryptionConfiguration echoed verbatim | PASS | SSE_S3 + KmsKey echoed on GetQueryExecution | 300.598 |
| QueryExecutionContext.Catalog=AwsDataCatalog round-trips | PASS | 180edbae-efad-4bc9-a3c4-370f84b6f922 SUCCEEDED; catalog echoed | 271.365 |
