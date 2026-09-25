## 01_smoke_and_endpoints

| feature | status | detail | latency_ms |
|---|---|---|---|
| endpoint routing (athena→emulator, s3/glue→moto) | PASS | athena=http://athena:5001 s3=http://moto:5000 glue=http://moto:5000 |  |
| boto3 start→poll→get_query_results | PASS | b3576953-2a80-40a6-b131-a95d8271b07e SUCCEEDED, 1 data row(s) | 516 |
| result artifacts on moto S3 (.csv + .csv.metadata) | PASS | results/b3576953-2a80-40a6-b131-a95d8271b07e.csv; results/b3576953-2a80-40a6-b131-a95d8271b07e.csv.metadata |  |
| wr.athena.read_sql_query (csv path) | PASS | shape=(1, 2) qid=2cac7724-c6db-41b0-acb8-12c9a9c99163 |  |
