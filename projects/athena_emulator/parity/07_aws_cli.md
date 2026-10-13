## 07_aws_cli

| feature | status | detail | latency_ms |
|---|---|---|---|
| aws binary + --endpoint-url routing (awscli 1.46.1) | PASS | /home/gabriel-menezes/Documents/repos/mlops/.venv/bin/aws → http://localhost:5001; list-work-groups → 1 group(s) incl. primary |  |
| create/get-work-group — configuration + create-time tags applied | PASS | nb07-wg-c9d7ca70 ENABLED, OutputLocation=s3://nb07-027ae2a26aff/results/ |  |
| update-work-group --state DISABLED + delete-work-group | PASS | nb07-team-c9d7ca70 DISABLED on read-back; absent from list after delete |  |
| list-tags-for-resource on a workgroup ARN | PASS | 3 create-time tag(s): ['Division', 'Location', 'Team'] |  |
| create/get/list/delete-data-catalog (LAMBDA + built-in GLUE) | PASS | nb07-dynamo-c9d7ca70 LAMBDA alongside AwsDataCatalog GLUE; nb07-unused-c9d7ca70 deleted |  |
| update-data-catalog via corrected --parameters form | PASS | doc --function flag is CLI-rejected; --parameters function=… rewrote description + function ARN |  |
| tag-resource / untag-resource / list-tags-for-resource on a catalog ARN | PASS | 4 tags applied, 4 remain after removing two unset keys |  |
| list-databases / get-database read the Glue catalog | PASS | nb07_sample_c9d7ca70 + nb07_geo_c9d7ca70 in DatabaseList |  |
| list-table-metadata / get-table-metadata | PASS | nb07_geo_c9d7ca70.regions listed; nb07_sample_c9d7ca70.counties fetched |  |
| create/get/list/delete-named-query under the workgroup | PASS | e97c35c0… created in nb07-wg-c9d7ca70, fetched, listed, deleted |  |
| batch-get-named-query splits found vs unprocessed ids | PASS | 1 found + 2 unprocessed sample ids |  |
| start-query-execution DDL (create database) → SUCCEEDED | PASS | 02571481… → s3://nb07-027ae2a26aff/results/02571481-68cc-42d7-b213-8d5e47b6c3c9.txt |  |
| CTAS seed via start-query-execution (DDL → Glue + parquet) | PASS | cloudfront_logs staged at s3://nb07-027ae2a26aff/cloudfront_logs/ |  |
| start → get-query-execution poll → .csv artifact (DML) | PASS | e4f1ddfd… SUCCEEDED; results/e4f1ddfd-33e9-4b85-9da8-64cf11ea022c.csv on moto | 1101.42 |
| get-query-results returns header row + data rows | PASS | 2 row(s), first=['2023-01-01', 'SFO'] |  |
| start-query-execution DDL variant (CREATE OR REPLACE VIEW) | PASS | cf10 built under nb07-wg-c9d7ca70 — shared primary untouched |  |
| list-query-executions + batch-get-query-execution | PASS | 4 execution id(s) in workgroup; batch → 1 found + 1 unprocessed |  |
| stop-query-execution cancels a running query | PASS | 0891ec1b… → CANCELLED |  |
