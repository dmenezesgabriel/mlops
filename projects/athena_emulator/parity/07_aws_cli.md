## 07_aws_cli

| feature | status | detail | latency_ms |
|---|---|---|---|
| aws binary + --endpoint-url routing (awscli 1.46.1) | PASS | /home/gabriel-menezes/Documents/repos/mlops/.venv/bin/aws → http://localhost:5001; list-work-groups → 1 group(s) incl. primary |  |
| create/get-work-group — configuration + create-time tags applied | PASS | nb07-wg-045e19ca ENABLED, OutputLocation=s3://nb07-4da4378ba56f/results/ |  |
| update-work-group --state DISABLED + delete-work-group | PASS | nb07-team-045e19ca DISABLED on read-back; absent from list after delete |  |
| list-tags-for-resource on a workgroup ARN | PASS | 3 create-time tag(s): ['Division', 'Location', 'Team'] |  |
| create/get/list/delete-data-catalog (LAMBDA + built-in GLUE) | PASS | nb07-dynamo-045e19ca LAMBDA alongside AwsDataCatalog GLUE; nb07-unused-045e19ca deleted |  |
| update-data-catalog via corrected --parameters form | PASS | doc --function flag is CLI-rejected; --parameters function=… rewrote description + function ARN |  |
| tag-resource / untag-resource / list-tags-for-resource on a catalog ARN | PASS | 4 tags applied, 4 remain after removing two unset keys |  |
| list-databases / get-database read the Glue catalog | PASS | nb07_sample_045e19ca + nb07_geo_045e19ca in DatabaseList |  |
| list-table-metadata / get-table-metadata | PASS | nb07_geo_045e19ca.regions listed; nb07_sample_045e19ca.counties fetched |  |
| create/get/list/delete-named-query under the workgroup | PASS | 3cca49e8… created in nb07-wg-045e19ca, fetched, listed, deleted |  |
| batch-get-named-query splits found vs unprocessed ids | PASS | 1 found + 2 unprocessed sample ids |  |
| start-query-execution DDL (create database) → SUCCEEDED | PASS | e83bb2c8… → s3://nb07-4da4378ba56f/results/e83bb2c8-85bc-4058-9d9e-a33202fc13f1.txt |  |
| CTAS seed via start-query-execution (DDL → Glue + parquet) | PASS | cloudfront_logs staged at s3://nb07-4da4378ba56f/cloudfront_logs/ |  |
| start → get-query-execution poll → .csv artifact (DML) | PASS | 0beb5dba… SUCCEEDED; results/0beb5dba-4fc2-4943-bf1e-875fb58c692b.csv on moto | 1857.74 |
| get-query-results returns header row + data rows | PASS | 2 row(s), first=['2023-01-01', 'SFO'] |  |
| start-query-execution DDL variant (CREATE OR REPLACE VIEW) | PASS | cf10 built under nb07-wg-045e19ca — shared primary untouched |  |
| list-query-executions + batch-get-query-execution | PASS | 4 execution id(s) in workgroup; batch → 1 found + 1 unprocessed |  |
| stop-query-execution cancels a running query | PASS | b2e08f48… → CANCELLED |  |
