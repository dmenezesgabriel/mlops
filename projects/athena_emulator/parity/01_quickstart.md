## 01_quickstart

| feature | status | detail | latency_ms |
|---|---|---|---|
| endpoint routing (athena→emulator, s3/glue→moto) | PASS | athena=http://localhost:5001 s3=http://localhost:5000 glue=http://localhost:5000 |  |
| boto3 start→poll→get_query_results | PASS | 7950de11-0fed-4a50-8b53-00a1dbdcc761 SUCCEEDED, 1 data row(s) | 516.411 |
| result artifacts on moto S3 (.csv + .csv.metadata) | PASS | results/7950de11-0fed-4a50-8b53-00a1dbdcc761.csv; results/7950de11-0fed-4a50-8b53-00a1dbdcc761.csv.metadata |  |
| wr.athena.read_sql_query (csv path) | PASS | shape=(1, 2) qid=76deda03-abe5-4028-9b28-eeead53fd3de |  |
