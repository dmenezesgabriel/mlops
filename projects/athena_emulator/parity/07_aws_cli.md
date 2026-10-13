## 07_aws_cli

| feature | status | detail | latency_ms |
|---|---|---|---|
| aws binary + --endpoint-url routing (awscli 1.46.1) | PASS | /home/gabriel-menezes/Documents/repos/mlops/.venv/bin/aws → http://localhost:5001; list-work-groups → 1 group(s) incl. primary |  |
| create/get-work-group — configuration + create-time tags applied | PASS | nb07-wg-3c614d39 ENABLED, OutputLocation=s3://nb07-e80dafbcf9de/results/ |  |
| update-work-group --state DISABLED + delete-work-group | PASS | nb07-team-3c614d39 DISABLED on read-back; absent from list after delete |  |
| list-tags-for-resource on a workgroup ARN | PASS | 3 create-time tag(s): ['Division', 'Location', 'Team'] |  |
| create/get/list/delete-data-catalog (LAMBDA + built-in GLUE) | PASS | nb07-dynamo-3c614d39 LAMBDA alongside AwsDataCatalog GLUE; nb07-unused-3c614d39 deleted |  |
| update-data-catalog via corrected --parameters form | PASS | doc --function flag is CLI-rejected; --parameters function=… rewrote description + function ARN |  |
| tag-resource / untag-resource / list-tags-for-resource on a catalog ARN | PASS | 4 tags applied, 4 remain after removing two unset keys |  |
| list-databases / get-database read the Glue catalog | PASS | nb07_sample_3c614d39 + nb07_geo_3c614d39 in DatabaseList |  |
| list-table-metadata / get-table-metadata | PASS | nb07_geo_3c614d39.regions listed; nb07_sample_3c614d39.counties fetched |  |
| create/get/list/delete-named-query under the workgroup | PASS | 9ec7163d… created in nb07-wg-3c614d39, fetched, listed, deleted |  |
| batch-get-named-query splits found vs unprocessed ids | PASS | 1 found + 2 unprocessed sample ids |  |
| start-query-execution DDL (create database) → SUCCEEDED | PASS | 3ddf29b9… → s3://nb07-e80dafbcf9de/results/3ddf29b9-e76a-4a6a-8f27-7f297299e168.txt |  |
| CTAS seed via start-query-execution (DDL → Glue + parquet) | PASS | cloudfront_logs staged at s3://nb07-e80dafbcf9de/cloudfront_logs/ |  |
| start → get-query-execution poll → .csv artifact (DML) | PASS | 1e9048e6… SUCCEEDED; results/1e9048e6-6876-4777-8321-d375ebf36351.csv on moto | 1222.11 |
| get-query-results returns header row + data rows | PASS | 2 row(s), first=['2023-01-01', 'SFO'] |  |
| start-query-execution DDL variant (CREATE OR REPLACE VIEW) | PASS | cf10 built under nb07-wg-3c614d39 — shared primary untouched |  |
| list-query-executions + batch-get-query-execution | PASS | 4 execution id(s) in workgroup; batch → 1 found + 1 unprocessed |  |
| stop-query-execution cancels a running query | PASS | 61c8bb36… → CANCELLED |  |
