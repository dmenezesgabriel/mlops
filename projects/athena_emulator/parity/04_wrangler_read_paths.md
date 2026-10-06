## 04_wrangler_read_paths

| feature | status | detail | latency_ms |
|---|---|---|---|
| wr.s3.to_parquet(dataset=True) registers Glue tables incl. partitions | PASS | nb04_people_e74ede2c: 3 columns registered; nb04_sales_e74ede2c: 2 partitions ['EU', 'US'] |  |
| read_sql_query csv path reads a wrangler-registered table | PASS | 5eabbb46-e7de-4709-9c79-7ca392a2ba4e shape=(3, 3) — Trino resolved the Glue-registered parquet table | 1340.56 |
| read_sql_query ctas_approach (temp CTAS → manifest → parquet read) | PASS | 0c4af262-6f39-4e0c-8dc0-9e9dc247544a rows=1; manifest=0c4af262-6f39-4e0c-8dc0-9e9dc247544a-manifest.csv | 1313.1 |
| read_sql_query api path (managed workgroup → inline GetQueryResults) | PASS | 6e017fe5-8e9e-481e-b1a0-4763c3254826 ResultConfiguration={}; 1 row(s) served inline | 228.516 |
| athena_cache_settings cache hit reuses the first execution | PASS | both reads → 9cefe399-e84d-4801-bd21-aa70dd59834b; list+batch_get supplied the hit |  |
| read_sql_query categories → pandas Categorical | PASS | region dtype=category |  |
| read_sql_query chunksize=2 → iterator of row-bounded frames | PASS | chunk row counts=[2, 1] |  |
| read_sql_query dtype_backend="pyarrow" | PASS | dtypes=['int32[pyarrow]', 'double[pyarrow]'] |  |
| read_sql_query params (named → client-side format) | PASS | WHERE region = 'EU' pruned read → 1 row |  |
| read_sql_query params (qmark → server-side ExecutionParameters) | PASS | 1ccd2026-1ea5-41e2-8b10-b612e87515db bound server-side → 1 row; ExecutionParameters echoed=['EU'] |  |
| read_sql_table reads the full registered table | PASS | shape=(3, 3) |  |
| get_query_results fetches the csv artifact of a DML SELECT | PASS | 9cefe399… → shape=(1, 2) |  |
| get_query_results fetches manifest parquet of a CTAS execution | PASS | 0c4af262… → shape=(1, 2) |  |
| list_query_executions returns the workgroup's execution ids | PASS | 66 id(s) incl. 9cefe399… |  |
| get_query_executions batch_gets into frames (+ unprocessed ids) | PASS | 2 execution rows + 1 unprocessed |  |
| get_query_execution returns the execution member | PASS | 9cefe399… Status.State=SUCCEEDED |  |
| wait_query returns on a terminal execution | PASS | 9cefe399… returned SUCCEEDED |  |
| describe_table returns the table's column listing | PASS | columns=['id', 'name', 'score'] |  |
| show_create_table returns the CREATE TABLE statement | PASS | CREATE TABLE hive.nb04_e74ede2c.nb04_people_e74ede2c ( |  |
| get_query_columns_types maps ColumnInfo Name/Type | PASS | {'seven': 'integer', 'label': 'varchar(6)'} |  |
| get_query_columns_types formats decimal precision/scale | PASS | {'amount': 'decimal(6, 2)'} |  |
| create_athena_bucket creates the default results bucket | PASS | s3://aws-athena-query-results-123456789012-us-east-1/ exists on moto |  |
| get_work_group returns primary's configuration | PASS | state=ENABLED enforce=False |  |
| read_sql_query unload_approach=True (UNLOAD → parquet read) | PASS | shape=(1, 2) |  |
| wr.athena.unload() writes a result set to S3 via UNLOAD | PASS | unloaded under s3://nb04-7e03cef2ab16/unload/ |  |
| repair_table (MSCK REPAIR TABLE) discovers new partitions | PASS | final state SUCCEEDED |  |
| SHOW PARTITIONS <table> (Athena spelling) | PASS | rows=0 |  |
| "<table>$partitions" virtual table lists Glue partitions | PASS | Glue partitions=['EU', 'US', 'XX'] |  |
