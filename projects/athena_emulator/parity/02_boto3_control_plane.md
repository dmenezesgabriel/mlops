## 02_boto3_control_plane

| feature | status | detail | latency_ms |
|---|---|---|---|
| primary workgroup seeded (ENABLED, enforce=False, engine AUTO/3) | PASS | state=ENABLED enforce=False |  |
| workgroup create/get/update/list (defaults applied) | PASS | nb02-wg-db41f208: enforce=True default, BytesScannedCutoffPerQuery 10485760→20971520 via ConfigurationUpdates |  |
| workgroup error taxonomy (duplicate/missing/primary-delete → 400) | PASS | InvalidRequestException 400 for all three |  |
| enforced workgroup overrides client OutputLocation | PASS | client passed s3://nb02-72a50fdb5dbc/client-prefix/; reported+written=s3://nb02-72a50fdb5dbc/wg-enforced/b0d5b44f-4789-46f5-b947-9b29940720d4.csv | 329.683 |
| non-enforced workgroup OutputLocation fallback | PASS | request omitted ResultConfiguration; reported+written=s3://nb02-72a50fdb5dbc/wg-fallback/10c8aaf1-cf9a-4d24-a7d5-397f1e817a64.csv | 287.07 |
| managed-results workgroup (no OutputLocation, inline rows, no S3 writes) | PASS | ResultConfiguration={}; rows=1; ignored/ empty | 289.825 |
| disabled workgroup rejects StartQueryExecution | PASS | InvalidRequestException (400) |  |
| named queries create/get/list (MaxResults+NextToken pagination) | PASS | 2 queries in nb02-wg-db41f208, first-page token='1' |  |
| named queries batch_get unprocessed IDs + delete→400 | PASS | unprocessed=['00000000-0000-0000-0000-000000000000']; deleted get → InvalidRequestException |  |
| prepared statements create/get/update/list/batch_get | PASS | nb02_stmt_db41f208 in nb02-wg-db41f208; unprocessed names surfaced |  |
| prepared statements missing/deleted → ResourceNotFoundException 404 | PASS | get/update/get-after-delete all 404 |  |
| data catalogs CRUD + AwsDataCatalog seed + LAMBDA normalization | PASS | AwsDataCatalog=GLUE; function→catalog/metadata-function/record-function; FEDERATED→400; missing→400 |  |
| tags tag/untag/list on workgroup + datacatalog ARNs | PASS | create-time tag present; +owner/-project on workgroup; kind=parity on datacatalog |  |
| tag error taxonomy (unknown → 404, malformed/non-taggable → 400) | PASS | RNFE 404 for unknown workgroup ARN; InvalidRequestException for bad ARN and preparedstatement type |  |
| list_work_groups honors MaxResults/NextToken | PASS | 1 workgroup + NextToken='1' |  |
| list_engine_versions (single AUTO/engine-3 entry) | PASS | 1 version(s): Athena engine version 3 |  |
