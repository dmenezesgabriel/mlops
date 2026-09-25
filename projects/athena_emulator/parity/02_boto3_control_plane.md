## 02_boto3_control_plane

| feature | status | detail | latency_ms |
|---|---|---|---|
| primary workgroup seeded (ENABLED, enforce=False, engine AUTO/3) | PASS | state=ENABLED enforce=False |  |
| workgroup create/get/update/list (defaults applied) | PASS | nb02-wg-42e66a0d: enforce=True default, BytesScannedCutoffPerQuery 10485760→20971520 via ConfigurationUpdates |  |
| workgroup error taxonomy (duplicate/missing/primary-delete → 400) | PASS | InvalidRequestException 400 for all three |  |
| enforced workgroup overrides client OutputLocation | PASS | client passed s3://nb02-035c513ad464/client-prefix/; reported+written=s3://nb02-035c513ad464/wg-enforced/5cfdd5eb-39a8-48ba-89f9-9e8e2b4692d0.csv | 264 |
| non-enforced workgroup OutputLocation fallback | PASS | request omitted ResultConfiguration; reported+written=s3://nb02-035c513ad464/wg-fallback/54e4e770-d163-478d-960d-bd5c925b9f59.csv | 260 |
| managed-results workgroup (no OutputLocation, inline rows, no S3 writes) | PASS | ResultConfiguration={}; rows=1; ignored/ empty | 261 |
| disabled workgroup rejects StartQueryExecution | GAP | b92dd449-24fa-4043-8988-4d3667b4f849 reached SUCCEEDED on a DISABLED workgroup; real AWS rejects at submit |  |
| named queries create/get/list (MaxResults+NextToken pagination) | PASS | 2 queries in nb02-wg-42e66a0d, first-page token='1' |  |
| named queries batch_get unprocessed IDs + delete→400 | PASS | unprocessed=['00000000-0000-0000-0000-000000000000']; deleted get → InvalidRequestException |  |
| prepared statements create/get/update/list/batch_get | PASS | nb02_stmt_42e66a0d in nb02-wg-42e66a0d; unprocessed names surfaced |  |
| prepared statements missing/deleted → ResourceNotFoundException 404 | PASS | get/update/get-after-delete all 404 |  |
| data catalogs CRUD + AwsDataCatalog seed + LAMBDA normalization | PASS | AwsDataCatalog=GLUE; function→catalog/metadata-function/record-function; FEDERATED→400; missing→400 |  |
| tags tag/untag/list on workgroup + datacatalog ARNs | PASS | create-time tag present; +owner/-project on workgroup; kind=parity on datacatalog |  |
| tag error taxonomy (unknown → 404, malformed/non-taggable → 400) | PASS | RNFE 404 for unknown workgroup ARN; InvalidRequestException for bad ARN and preparedstatement type |  |
| list_work_groups honors MaxResults/NextToken | GAP | MaxResults=1 returned 6 workgroups, NextToken=False |  |
| list_engine_versions (single AUTO/engine-3 entry) | PASS | 1 version(s): Athena engine version 3 |  |
