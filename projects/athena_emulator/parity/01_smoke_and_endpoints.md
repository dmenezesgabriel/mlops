## 01_smoke_and_endpoints

| feature | status | detail | latency_ms |
|---|---|---|---|
| endpoint routing (athena→emulator, s3/glue→moto) | PASS | athena=http://localhost:5001 s3=http://localhost:5000 glue=http://localhost:5000 |  |
| boto3 start→poll→get_query_results | PASS | 8f0c8c12-9d0d-4215-af7f-627f4abbee56 SUCCEEDED, 1 data row(s) | 520.457 |
| result artifacts on moto S3 (.csv + .csv.metadata) | PASS | results/8f0c8c12-9d0d-4215-af7f-627f4abbee56.csv; results/8f0c8c12-9d0d-4215-af7f-627f4abbee56.csv.metadata |  |
| wr.athena.read_sql_query (csv path) | PASS | shape=(1, 2) qid=6142bdba-662c-4ca6-820f-4aff4f1b0987 |  |
