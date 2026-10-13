## 01_quickstart

| feature | status | detail | latency_ms |
|---|---|---|---|
| endpoint routing (athena→emulator, s3/glue→moto) | PASS | athena=http://localhost:5001 s3=http://localhost:5000 glue=http://localhost:5000 |  |
| boto3 start→poll→get_query_results | PASS | c58fb03c-6ce9-4f6e-9d4c-4cfd7deaa4c1 SUCCEEDED, 1 data row(s) | 522.758 |
| result artifacts on moto S3 (.csv + .csv.metadata) | PASS | results/c58fb03c-6ce9-4f6e-9d4c-4cfd7deaa4c1.csv; results/c58fb03c-6ce9-4f6e-9d4c-4cfd7deaa4c1.csv.metadata |  |
| wr.athena.read_sql_query (csv path) | PASS | shape=(1, 2) qid=aa32988a-5fe0-4b55-9b9a-2a18b8c0fabc |  |
