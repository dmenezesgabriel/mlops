## 01_quickstart

| feature | status | detail | latency_ms |
|---|---|---|---|
| endpoint routing (athena→emulator, s3/glue→moto) | PASS | athena=http://localhost:5001 s3=http://localhost:5000 glue=http://localhost:5000 |  |
| boto3 start→poll→get_query_results | PASS | 83ecc92a-920c-4bc7-a4ec-872679581907 SUCCEEDED, 1 data row(s) | 2066.63 |
| result artifacts on moto S3 (.csv + .csv.metadata) | PASS | results/83ecc92a-920c-4bc7-a4ec-872679581907.csv; results/83ecc92a-920c-4bc7-a4ec-872679581907.csv.metadata |  |
| wr.athena.read_sql_query (csv path) | PASS | shape=(1, 2) qid=d062b39c-c7b1-437a-aa21-d6aff2daf4e7 |  |
