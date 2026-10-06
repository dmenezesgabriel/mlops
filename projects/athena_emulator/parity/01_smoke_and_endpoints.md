## 01_smoke_and_endpoints

| feature | status | detail | latency_ms |
|---|---|---|---|
| endpoint routing (athena→emulator, s3/glue→moto) | PASS | athena=http://localhost:5001 s3=http://localhost:5000 glue=http://localhost:5000 |  |
| boto3 start→poll→get_query_results | PASS | 57532c9e-370a-4806-abf8-6c79394a7c2b SUCCEEDED, 1 data row(s) | 569.717 |
| result artifacts on moto S3 (.csv + .csv.metadata) | PASS | results/57532c9e-370a-4806-abf8-6c79394a7c2b.csv; results/57532c9e-370a-4806-abf8-6c79394a7c2b.csv.metadata |  |
| wr.athena.read_sql_query (csv path) | PASS | shape=(1, 2) qid=150018b9-8c7c-4155-b834-62e2b64901ff |  |
