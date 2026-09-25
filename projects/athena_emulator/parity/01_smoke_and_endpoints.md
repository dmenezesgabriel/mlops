## 01_smoke_and_endpoints

| feature | status | detail | latency_ms |
|---|---|---|---|
| endpoint routing (athena→emulator, s3/glue→moto) | PASS | athena=http://athena:5001 s3=http://moto:5000 glue=http://moto:5000 |  |
| boto3 start→poll→get_query_results | PASS | ffcc7583-f9f9-491c-9cc1-14c11ad7f1c4 SUCCEEDED, 1 data row(s) | 516 |
| result artifacts on moto S3 (.csv + .csv.metadata) | PASS | results/ffcc7583-f9f9-491c-9cc1-14c11ad7f1c4.csv; results/ffcc7583-f9f9-491c-9cc1-14c11ad7f1c4.csv.metadata |  |
| wr.athena.read_sql_query (csv path) | PASS | shape=(1, 2) qid=629be279-5d1b-40e2-ac50-75b90521a10f |  |
