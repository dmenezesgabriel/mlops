## 01_smoke_and_endpoints

| feature | status | detail | latency_ms |
|---|---|---|---|
| endpoint routing (athena→emulator, s3/glue→moto) | PASS | athena=http://localhost:5001 s3=http://localhost:5000 glue=http://localhost:5000 |  |
| boto3 start→poll→get_query_results | PASS | 25391f75-b245-46d8-9fa0-4e9956ce87e3 SUCCEEDED, 1 data row(s) | 533.635 |
| result artifacts on moto S3 (.csv + .csv.metadata) | PASS | results/25391f75-b245-46d8-9fa0-4e9956ce87e3.csv; results/25391f75-b245-46d8-9fa0-4e9956ce87e3.csv.metadata |  |
| wr.athena.read_sql_query (csv path) | PASS | shape=(1, 2) qid=bd083b8a-f7ca-40fd-aaf2-6ae80ac71a1c |  |
