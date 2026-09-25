## 01_smoke_and_endpoints

| feature | status | detail | latency_ms |
|---|---|---|---|
| endpoint routing (athena→emulator, s3/glue→moto) | PASS | athena=http://athena:5001 s3=http://moto:5000 glue=http://moto:5000 |  |
| boto3 start→poll→get_query_results | PASS | 99e557c9-d0d7-48ed-a57f-3f3422bc0666 SUCCEEDED, 1 data row(s) | 547 |
| result artifacts on moto S3 (.csv + .csv.metadata) | PASS | results/99e557c9-d0d7-48ed-a57f-3f3422bc0666.csv; results/99e557c9-d0d7-48ed-a57f-3f3422bc0666.csv.metadata |  |
| wr.athena.read_sql_query (csv path) | PASS | shape=(1, 2) qid=b08cd71d-1c01-412a-a2b9-dfc391275f2a |  |
