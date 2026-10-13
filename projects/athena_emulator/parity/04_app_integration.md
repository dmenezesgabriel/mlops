## 04_app_integration

| feature | status | detail | latency_ms |
|---|---|---|---|
| start→poll→GetQueryExecution (SELECT) + .csv artifact | PASS | 118d6791-044b-4132-9ca4-1ad52b9596e4 SUCCEEDED DML/SELECT; OutputLocation=s3://nb04-01053428ac82/results/118d6791-044b-4132-9ca4-1ad52b9596e4.csv | 318.669 |
| GetQueryResults paginates (header on page 0, opaque NextToken) | PASS | 3 manual pages (3+2+1 rows); botocore paginator merged 6 rows losslessly |  |
| batch_get/list executions (unprocessed IDs, paged, newest first) | PASS | unknown id → UnprocessedQueryExecutionIds; MaxResults=1 paginated 2 executions newest-first |  |
| GetQueryRuntimeStatistics (Timeline + Rows shape) | PASS | EngineExecutionTimeInMillis=0 InputBytes=0 |  |
| StopQueryExecution → CANCELLED | PASS | f7d391f1-2bdd-4bc0-8327-76342e48216d CANCELLED |  |
| stop on a terminal execution (AWS no-ops with 200) | PASS | 200 no-op on a SUCCEEDED execution |  |
| named queries create/get/list (MaxResults+NextToken pagination) | PASS | 2 queries in nb04-wg-c1787d25, first-page token='1' |  |
| named queries batch_get unprocessed IDs + delete→400 | PASS | unprocessed=['00000000-0000-0000-0000-000000000000']; deleted get → InvalidRequestException |  |
| prepared statements create/get/update/list/batch_get | PASS | nb04_stmt_c1787d25 in nb04-wg-c1787d25; unprocessed names surfaced |  |
| prepared statements missing/deleted → ResourceNotFoundException 404 | PASS | missing get/update + deleted get → 404 |  |
| EXECUTE + ExecutionParameters binds and echoes | PASS | nb04_stmt_c1787d25 → row 'hello'; ExecutionParameters echoed | 283.006 |
| qmark ExecutionParameters on a plain query | PASS | SELECT ? with ['42'] → row '42' | 287.138 |
| EXECUTE failures → FAILED not 400 (missing stmt, ?-count) | PASS | both FAILED with Athena's StateChangeReason phrasing |  |
| ClientRequestToken dedupes retried submissions | PASS | token 0848a2f1… → single execution cc0749d3… |  |
| ResultReuseConfiguration reuses recent results | PASS | second identical run reused (ReusedPreviousResult=True) |  |
| ResultConfiguration.EncryptionConfiguration echoed verbatim | PASS | SSE_S3 + KmsKey echoed on GetQueryExecution | 282.897 |
| QueryExecutionContext.Catalog=AwsDataCatalog round-trips | PASS | 0ae97f67-6ff7-4867-bdcf-e5fb9593e711 SUCCEEDED; catalog echoed | 292.335 |
