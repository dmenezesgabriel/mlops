## 01_smoke_and_endpoints

| feature | status | detail | latency_ms |
|---|---|---|---|
| endpoint routing (athena→emulator, s3/glue→moto) | PASS | athena=http://athena:5001 s3=http://moto:5000 glue=http://moto:5000 |  |
| boto3 start→poll→get_query_results | PASS | 7bb9fb90-7c36-472c-92b9-dac40edd6bde SUCCEEDED, 1 data row(s) | 552 |
| result artifacts on moto S3 (.csv + .csv.metadata) | PASS | results/7bb9fb90-7c36-472c-92b9-dac40edd6bde.csv; results/7bb9fb90-7c36-472c-92b9-dac40edd6bde.csv.metadata |  |
| wr.athena.read_sql_query (csv path) | PASS | shape=(1, 2) qid=64ac4b5c-4820-4c21-8f3f-f6f57099522d |  |
