## 05_governance

| feature | status | detail | latency_ms |
|---|---|---|---|
| primary workgroup seeded (ENABLED, enforce=False, engine AUTO/3) | PASS | state=ENABLED enforce=False |  |
| list_engine_versions (single AUTO/engine-3 entry) | PASS | 1 version(s): Athena engine version 3 |  |
| workgroup create/get/update/list (defaults applied) | PASS | nb05-wg-151e60a6: enforce=True default, BytesScannedCutoffPerQuery 10485760→20971520→removed via ConfigurationUpdates |  |
| workgroup error taxonomy (duplicate/missing/primary-delete → 400) | PASS | InvalidRequestException 400 for all three |  |
| enforced workgroup overrides client OutputLocation | PASS | client passed s3://nb05-69f220db6c6c/client-prefix/; reported+written=s3://nb05-69f220db6c6c/wg-enforced/19243d58-4d35-463b-8aea-40ac30dbe700.csv | 290.145 |
| non-enforced workgroup OutputLocation fallback | PASS | request omitted ResultConfiguration; reported+written=s3://nb05-69f220db6c6c/wg-fallback/af02e841-5304-438b-b002-c06b626cbb24.csv | 282.918 |
| managed-results workgroup (no OutputLocation, inline rows, no S3 writes) | PASS | ResultConfiguration={}; rows=1; ignored/ empty | 288.015 |
| disabled workgroup rejects StartQueryExecution | PASS | InvalidRequestException (400) |  |
| workgroup EncryptionConfiguration echoed verbatim on GetWorkGroup | PASS | SSE_KMS + KmsKey echoed: {'EncryptionOption': 'SSE_KMS', 'KmsKey': 'arn:aws:kms:us-east-1:123456789012:key/00000000-0000-0000-0000-000000000000'} |  |
| data catalogs CRUD + AwsDataCatalog seed + LAMBDA normalization | PASS | AwsDataCatalog=GLUE; function→catalog/metadata-function/record-function; FEDERATED→400; missing→400 |  |
| tags tag/untag/list on workgroup + datacatalog ARNs | PASS | create-time tag present; +owner/-project on workgroup; kind=parity on datacatalog |  |
| tag error taxonomy (unknown → 404, malformed/non-taggable → 400) | PASS | RNFE 404 for unknown workgroup ARN; InvalidRequestException for bad ARN and preparedstatement type |  |
| list_work_groups honors MaxResults/NextToken | PASS | 1 workgroup + NextToken='1' |  |
