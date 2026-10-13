## 01_quickstart

| feature | status | detail | latency_ms |
|---|---|---|---|
| endpoint routing (athena→emulator, s3/glue→moto) | PASS | athena=http://localhost:5001 s3=http://localhost:5000 glue=http://localhost:5000 |  |
| boto3 start→poll→get_query_results | PASS | a6e3b0f6-09a3-4686-a07f-8e3ba9ccec23 SUCCEEDED, 1 data row(s) | 3466.38 |
| result artifacts on moto S3 (.csv + .csv.metadata) | PASS | results/a6e3b0f6-09a3-4686-a07f-8e3ba9ccec23.csv; results/a6e3b0f6-09a3-4686-a07f-8e3ba9ccec23.csv.metadata |  |
| wr.athena.read_sql_query (csv path) | PASS | shape=(1, 2) qid=39e9830d-f604-42c2-821d-01fe10ff56fc |  |
