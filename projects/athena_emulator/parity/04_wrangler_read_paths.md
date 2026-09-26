## 04_wrangler_read_paths

| feature | status | detail | latency_ms |
|---|---|---|---|
| wr.s3.to_parquet(dataset=True) registers Glue tables incl. partitions | PASS | nb04_people_e2027657: 3 columns registered; nb04_sales_e2027657: 2 partitions ['EU', 'US'] |  |
| read_sql_query csv path reads a wrangler-registered table | PASS | d101b5bb-36f7-4be4-9266-20f6c4f7dfe4 shape=(3, 3) — Trino resolved the Glue-registered parquet table | 1080 |
| read_sql_query ctas_approach (temp CTAS → manifest → parquet read) | PASS | ef4e6ec2-4eab-4d50-916b-143a79c0b75d rows=1; manifest=ef4e6ec2-4eab-4d50-916b-143a79c0b75d-manifest.csv | 1154 |
| read_sql_query api path (managed workgroup → inline GetQueryResults) | PASS | 01d071cc-7cac-45ba-b50e-0bf8abaf36aa ResultConfiguration={}; 1 row(s) served inline | 1067 |
| athena_cache_settings cache hit reuses the first execution | PASS | both reads → 676577a1-3199-4d08-b2af-934725e4f0dd; list+batch_get supplied the hit |  |
| read_sql_query categories → pandas Categorical | PASS | region dtype=category |  |
| read_sql_query chunksize=2 → iterator of row-bounded frames | PASS | chunk row counts=[2, 1] |  |
| read_sql_query dtype_backend="pyarrow" | PASS | dtypes=['int32[pyarrow]', 'double[pyarrow]'] |  |
| read_sql_query params (named → client-side format) | PASS | WHERE region = 'EU' pruned read → 1 row |  |
| read_sql_query params (qmark → server-side ExecutionParameters) | PASS | bc2484ae-94f4-45a8-b7b0-d8cad22968ad bound server-side → 1 row; ExecutionParameters echoed=['EU'] |  |
| read_sql_table reads the full registered table | PASS | shape=(3, 3) |  |
| get_query_results fetches the csv artifact of a DML SELECT | PASS | 676577a1… → shape=(1, 2) |  |
| get_query_results fetches manifest parquet of a CTAS execution | PASS | ef4e6ec2… → shape=(1, 2) |  |
| list_query_executions returns the workgroup's execution ids | PASS | 14 id(s) incl. 676577a1… |  |
| get_query_executions batch_gets into frames (+ unprocessed ids) | PASS | 2 execution rows + 1 unprocessed |  |
| get_query_execution returns the execution member | PASS | 676577a1… Status.State=SUCCEEDED |  |
| wait_query returns on a terminal execution | PASS | 676577a1… returned SUCCEEDED |  |
| describe_table returns the table's column listing | PASS | columns=['id', 'name', 'score'] |  |
| show_create_table returns the CREATE TABLE statement | PASS | CREATE TABLE hive.nb04_e2027657.nb04_people_e2027657 ( |  |
| get_query_columns_types maps ColumnInfo Name/Type | PASS | {'seven': 'integer', 'label': 'varchar(6)'} |  |
| get_query_columns_types formats decimal precision/scale | PASS | {'amount': 'decimal(6, 2)'} |  |
| create_athena_bucket creates the default results bucket | PASS | s3://aws-athena-query-results-123456789012-us-east-1/ exists on moto |  |
| get_work_group returns primary's configuration | PASS | state=ENABLED enforce=False |  |
| read_sql_query unload_approach=True (UNLOAD → parquet read) | PASS | shape=(1, 2) |  |
| wr.athena.unload() writes a result set to S3 via UNLOAD | PASS | unloaded under s3://nb04-dd95b4de7861/unload/ |  |
| repair_table (MSCK REPAIR TABLE) discovers new partitions | PASS | final state SUCCEEDED |  |
| SHOW PARTITIONS <table> (Athena spelling) | PASS | rows=0 |  |
| "<table>$partitions" virtual table lists Glue partitions | PASS | Glue partitions=['EU', 'US', 'XX'] |  |
