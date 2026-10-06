## 04_wrangler_read_paths

| feature | status | detail | latency_ms |
|---|---|---|---|
| wr.s3.to_parquet(dataset=True) registers Glue tables incl. partitions | PASS | nb04_people_120dfb2d: 3 columns registered; nb04_sales_120dfb2d: 2 partitions ['EU', 'US'] |  |
| read_sql_query csv path reads a wrangler-registered table | PASS | e7a53b4c-9419-49e5-90e9-0c5c41f9723f shape=(3, 3) — Trino resolved the Glue-registered parquet table | 1206.98 |
| read_sql_query ctas_approach (temp CTAS → manifest → parquet read) | PASS | 6699b527-eff0-4513-ae92-c30d636c0bb7 rows=1; manifest=6699b527-eff0-4513-ae92-c30d636c0bb7-manifest.csv | 1263.72 |
| read_sql_query api path (managed workgroup → inline GetQueryResults) | PASS | 785bcbe7-b924-4a9e-a563-928e4df101c8 ResultConfiguration={}; 1 row(s) served inline | 1184.15 |
| athena_cache_settings cache hit reuses the first execution | PASS | both reads → 11ad7612-76a5-4af0-b2ba-9f27efbbd239; list+batch_get supplied the hit |  |
| read_sql_query categories → pandas Categorical | PASS | region dtype=category |  |
| read_sql_query chunksize=2 → iterator of row-bounded frames | PASS | chunk row counts=[2, 1] |  |
| read_sql_query dtype_backend="pyarrow" | PASS | dtypes=['int32[pyarrow]', 'double[pyarrow]'] |  |
| read_sql_query params (named → client-side format) | PASS | WHERE region = 'EU' pruned read → 1 row |  |
| read_sql_query params (qmark → server-side ExecutionParameters) | PASS | 4eb6800b-f940-4d5e-aefc-2425748abcbb bound server-side → 1 row; ExecutionParameters echoed=['EU'] |  |
| read_sql_table reads the full registered table | PASS | shape=(3, 3) |  |
| get_query_results fetches the csv artifact of a DML SELECT | PASS | 11ad7612… → shape=(1, 2) |  |
| get_query_results fetches manifest parquet of a CTAS execution | PASS | 6699b527… → shape=(1, 2) |  |
| list_query_executions returns the workgroup's execution ids | PASS | 38 id(s) incl. 11ad7612… |  |
| get_query_executions batch_gets into frames (+ unprocessed ids) | PASS | 2 execution rows + 1 unprocessed |  |
| get_query_execution returns the execution member | PASS | 11ad7612… Status.State=SUCCEEDED |  |
| wait_query returns on a terminal execution | PASS | 11ad7612… returned SUCCEEDED |  |
| describe_table returns the table's column listing | PASS | columns=['id', 'name', 'score'] |  |
| show_create_table returns the CREATE TABLE statement | PASS | CREATE TABLE hive.nb04_120dfb2d.nb04_people_120dfb2d ( |  |
| get_query_columns_types maps ColumnInfo Name/Type | PASS | {'seven': 'integer', 'label': 'varchar(6)'} |  |
| get_query_columns_types formats decimal precision/scale | PASS | {'amount': 'decimal(6, 2)'} |  |
| create_athena_bucket creates the default results bucket | PASS | s3://aws-athena-query-results-123456789012-us-east-1/ exists on moto |  |
| get_work_group returns primary's configuration | PASS | state=ENABLED enforce=False |  |
| read_sql_query unload_approach=True (UNLOAD → parquet read) | PASS | shape=(1, 2) |  |
| wr.athena.unload() writes a result set to S3 via UNLOAD | PASS | unloaded under s3://nb04-2c607c0e9703/unload/ |  |
| repair_table (MSCK REPAIR TABLE) discovers new partitions | PASS | final state SUCCEEDED |  |
| SHOW PARTITIONS <table> (Athena spelling) | PASS | rows=0 |  |
| "<table>$partitions" virtual table lists Glue partitions | PASS | Glue partitions=['EU', 'US', 'XX'] |  |
