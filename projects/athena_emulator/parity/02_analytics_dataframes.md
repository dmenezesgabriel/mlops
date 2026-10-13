## 02_analytics_dataframes

| feature | status | detail | latency_ms |
|---|---|---|---|
| read_sql_query csv path reads a wrangler-registered table | PASS | 0d4feda6-e4e3-4431-921e-ad76d71b5499 shape=(3, 3) — Trino resolved the Glue-registered parquet table | 1072.27 |
| read_sql_query ctas_approach (temp CTAS → manifest → parquet read) | PASS | 432f680d-b9c9-44a8-8796-762c88dfaac3 rows=1; manifest=432f680d-b9c9-44a8-8796-762c88dfaac3-manifest.csv | 1080.91 |
| read_sql_query api path (managed workgroup → inline GetQueryResults) | PASS | 104343b6-f72a-445b-bf0b-c864bd282d64 ResultConfiguration={}; 1 row(s) served inline | 1053.43 |
| athena_cache_settings cache hit reuses the first execution | PASS | both reads → 0f6f26ff-6fa7-4049-87eb-eb9be4a9f691; list+batch_get supplied the hit |  |
| read_sql_query categories → pandas Categorical | PASS | region dtype=category |  |
| read_sql_query chunksize=2 → iterator of row-bounded frames | PASS | chunk row counts=[2, 1] |  |
| read_sql_query dtype_backend="pyarrow" | PASS | dtypes=['int32[pyarrow]', 'double[pyarrow]'] |  |
| read_sql_query params (named → client-side format) | PASS | WHERE region = 'EU' pruned read → 1 row |  |
| read_sql_query params (qmark → server-side ExecutionParameters) | PASS | e1ed43c1-f2ab-4312-bb99-a0dd0641756d bound server-side → 1 row; ExecutionParameters echoed=['EU'] |  |
| read_sql_table reads the full registered table | PASS | shape=(3, 3) |  |
| get_query_results fetches the csv artifact of a DML SELECT | PASS | 0f6f26ff… → shape=(1, 2) |  |
| get_query_results fetches manifest parquet of a CTAS execution | PASS | 432f680d… → shape=(1, 2) |  |
| list_query_executions returns the workgroup's execution ids | PASS | 52 id(s) incl. 0f6f26ff… |  |
| get_query_executions batch_gets into frames (+ unprocessed ids) | PASS | 2 execution rows + 1 unprocessed |  |
| get_query_execution returns the execution member | PASS | 0f6f26ff… Status.State=SUCCEEDED |  |
| wait_query returns on a terminal execution | PASS | 0f6f26ff… returned SUCCEEDED |  |
| describe_table returns the table's column listing | PASS | columns=['id', 'name', 'score'] |  |
| show_create_table returns the CREATE TABLE statement | PASS | CREATE TABLE hive.nb02_0e2866f8.nb02_people_0e2866f8 ( |  |
| get_query_columns_types maps ColumnInfo Name/Type | PASS | {'seven': 'integer', 'label': 'varchar(6)'} |  |
| get_query_columns_types formats decimal precision/scale | PASS | {'amount': 'decimal(6, 2)'} |  |
| create_athena_bucket creates the default results bucket | PASS | s3://aws-athena-query-results-123456789012-us-east-1/ exists on moto |  |
| get_work_group returns primary's configuration | PASS | state=ENABLED enforce=False |  |
