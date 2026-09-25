## 02_boto3_control_plane

| feature | status | detail | latency_ms |
|---|---|---|---|
| primary workgroup seeded (ENABLED, enforce=False, engine AUTO/3) | PASS | state=ENABLED enforce=False |  |
| workgroup create/get/update/list (defaults applied) | PASS | nb02-wg-bf8358c1: enforce=True default, BytesScannedCutoffPerQuery 10485760→20971520 via ConfigurationUpdates |  |
| workgroup error taxonomy (duplicate/missing/primary-delete → 400) | PASS | InvalidRequestException 400 for all three |  |
| enforced workgroup overrides client OutputLocation | PASS | client passed s3://nb02-cf018db4396b/client-prefix/; reported+written=s3://nb02-cf018db4396b/wg-enforced/415571f8-38f1-411b-87bf-c82f3a0fd859.csv | 262 |
| non-enforced workgroup OutputLocation fallback | PASS | request omitted ResultConfiguration; reported+written=s3://nb02-cf018db4396b/wg-fallback/5767c78e-7766-4a4e-b249-dc3f9c26e38a.csv | 259 |
| managed-results workgroup (no OutputLocation, inline rows, no S3 writes) | PASS | ResultConfiguration={}; rows=1; ignored/ empty | 259 |
| disabled workgroup rejects StartQueryExecution | GAP | a9fab625-067d-48ac-a81a-b4d3d4eef6a5 reached SUCCEEDED on a DISABLED workgroup; real AWS rejects at submit |  |
| named queries create/get/list (MaxResults+NextToken pagination) | PASS | 2 queries in nb02-wg-bf8358c1, first-page token='1' |  |
| named queries batch_get unprocessed IDs + delete→400 | PASS | unprocessed=['00000000-0000-0000-0000-000000000000']; deleted get → InvalidRequestException |  |
| prepared statements create/get/update/list/batch_get | PASS | nb02_stmt_bf8358c1 in nb02-wg-bf8358c1; unprocessed names surfaced |  |
| prepared statements missing/deleted → ResourceNotFoundException 404 | PASS | get/update/get-after-delete all 404 |  |
| data catalogs CRUD + AwsDataCatalog seed + LAMBDA normalization | PASS | AwsDataCatalog=GLUE; function→catalog/metadata-function/record-function; FEDERATED→400; missing→400 |  |
| tags tag/untag/list on workgroup + datacatalog ARNs | PASS | create-time tag present; +owner/-project on workgroup; kind=parity on datacatalog |  |
| tag error taxonomy (unknown → 404, malformed/non-taggable → 400) | PASS | RNFE 404 for unknown workgroup ARN; InvalidRequestException for bad ARN and preparedstatement type |  |
| list_work_groups honors MaxResults/NextToken | GAP | MaxResults=1 returned 6 workgroups, NextToken=False |  |
| list_engine_versions (single AUTO/engine-3 entry) | PASS | 1 version(s): Athena engine version 3 |  |
