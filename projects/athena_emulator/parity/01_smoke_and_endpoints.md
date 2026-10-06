## 01_smoke_and_endpoints

| feature | status | detail | latency_ms |
|---|---|---|---|
| endpoint routing (athena→emulator, s3/glue→moto) | PASS | athena=http://localhost:5001 s3=http://localhost:5000 glue=http://localhost:5000 |  |
| boto3 start→poll→get_query_results | PASS | 77c76686-10db-4c09-934b-956cec769f2c SUCCEEDED, 1 data row(s) | 548.507 |
| result artifacts on moto S3 (.csv + .csv.metadata) | PASS | results/77c76686-10db-4c09-934b-956cec769f2c.csv; results/77c76686-10db-4c09-934b-956cec769f2c.csv.metadata |  |
| wr.athena.read_sql_query (csv path) | PASS | shape=(1, 2) qid=e384f47c-75e3-4913-9eed-f7e7aecb1e94 |  |
