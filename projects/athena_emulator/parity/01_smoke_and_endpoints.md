## 01_smoke_and_endpoints

| feature | status | detail | latency_ms |
|---|---|---|---|
| endpoint routing (athena→emulator, s3/glue→moto) | PASS | athena=http://athena:5001 s3=http://moto:5000 glue=http://moto:5000 |  |
| boto3 start→poll→get_query_results | PASS | f757c44d-5071-4392-9e2a-4753e476aeea SUCCEEDED, 1 data row(s) | 535.532 |
| result artifacts on moto S3 (.csv + .csv.metadata) | PASS | results/f757c44d-5071-4392-9e2a-4753e476aeea.csv; results/f757c44d-5071-4392-9e2a-4753e476aeea.csv.metadata |  |
| wr.athena.read_sql_query (csv path) | PASS | shape=(1, 2) qid=a9f9caed-8d11-4f56-b87c-964d55a20afd |  |
