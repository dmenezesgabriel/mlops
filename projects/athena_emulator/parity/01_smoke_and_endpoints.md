## 01_smoke_and_endpoints

| feature | status | detail | latency_ms |
|---|---|---|---|
| endpoint routing (athena→emulator, s3/glue→moto) | PASS | athena=http://athena:5001 s3=http://moto:5000 glue=http://moto:5000 |  |
| boto3 start→poll→get_query_results | PASS | 4e2fd186-f582-4410-a35d-e91c854ae8ec SUCCEEDED, 1 data row(s) | 540 |
| result artifacts on moto S3 (.csv + .csv.metadata) | PASS | results/4e2fd186-f582-4410-a35d-e91c854ae8ec.csv; results/4e2fd186-f582-4410-a35d-e91c854ae8ec.csv.metadata |  |
| wr.athena.read_sql_query (csv path) | PASS | shape=(1, 2) qid=2cb91abe-7b55-4798-9839-d7231da9dcb5 |  |
