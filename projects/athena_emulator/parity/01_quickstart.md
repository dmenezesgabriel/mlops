## 01_quickstart

| feature | status | detail | latency_ms |
|---|---|---|---|
| endpoint routing (athena→emulator, s3/glue→moto) | PASS | athena=http://localhost:5001 s3=http://localhost:5000 glue=http://localhost:5000 |  |
| boto3 start→poll→get_query_results | PASS | 95d611db-571e-4b3c-a696-d868ff85425a SUCCEEDED, 1 data row(s) | 2630.77 |
| result artifacts on moto S3 (.csv + .csv.metadata) | PASS | results/95d611db-571e-4b3c-a696-d868ff85425a.csv; results/95d611db-571e-4b3c-a696-d868ff85425a.csv.metadata |  |
| wr.athena.read_sql_query (csv path) | PASS | shape=(1, 2) qid=40bf9ab6-bb76-44eb-a81b-216ae1d68bab |  |
