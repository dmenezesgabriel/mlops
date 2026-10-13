## 01_quickstart

| feature | status | detail | latency_ms |
|---|---|---|---|
| endpoint routing (athena→emulator, s3/glue→moto) | PASS | athena=http://localhost:5001 s3=http://localhost:5000 glue=http://localhost:5000 |  |
| boto3 start→poll→get_query_results | PASS | 86660956-1714-4842-a17b-37b214284f83 SUCCEEDED, 1 data row(s) | 515.157 |
| result artifacts on moto S3 (.csv + .csv.metadata) | PASS | results/86660956-1714-4842-a17b-37b214284f83.csv; results/86660956-1714-4842-a17b-37b214284f83.csv.metadata |  |
| wr.athena.read_sql_query (csv path) | PASS | shape=(1, 2) qid=eb1b0173-2d8a-46f3-ad72-f78194f5388b |  |
