## 01_quickstart

| feature | status | detail | latency_ms |
|---|---|---|---|
| endpoint routing (athena→emulator, s3/glue→moto) | PASS | athena=http://localhost:5001 s3=http://localhost:5000 glue=http://localhost:5000 |  |
| boto3 start→poll→get_query_results | PASS | 37cd8273-ce3a-466e-bffd-11d63561c6c0 SUCCEEDED, 1 data row(s) | 533.655 |
| result artifacts on moto S3 (.csv + .csv.metadata) | PASS | results/37cd8273-ce3a-466e-bffd-11d63561c6c0.csv; results/37cd8273-ce3a-466e-bffd-11d63561c6c0.csv.metadata |  |
| wr.athena.read_sql_query (csv path) | PASS | shape=(1, 2) qid=06d53969-f1d7-4840-a25f-d5ae0bbf8347 |  |
