## 02_analytics_dataframes

| feature | status | detail | latency_ms |
|---|---|---|---|
| read_sql_query csv path reads a wrangler-registered table | PASS | 183247f7-f815-4337-99ab-5aa062eb8525 shape=(3, 3) — Trino resolved the Glue-registered parquet table | 1150.73 |
| read_sql_query ctas_approach (temp CTAS → manifest → parquet read) | PASS | cbe7ece2-7387-4860-96d6-9b737bfb4582 rows=1; manifest=cbe7ece2-7387-4860-96d6-9b737bfb4582-manifest.csv | 1188.24 |
| read_sql_query api path (managed workgroup → inline GetQueryResults) | PASS | c60c255e-5cf3-47ee-9ce4-07390e556482 ResultConfiguration={}; 1 row(s) served inline | 1127.13 |
| athena_cache_settings cache hit reuses the first execution | PASS | both reads → 220ccbc1-09a6-44c8-a4ea-20f00e85d9f4; list+batch_get supplied the hit |  |
| read_sql_query categories → pandas Categorical | PASS | region dtype=category |  |
| read_sql_query chunksize=2 → iterator of row-bounded frames | PASS | chunk row counts=[2, 1] |  |
| read_sql_query dtype_backend="pyarrow" | PASS | dtypes=['int32[pyarrow]', 'double[pyarrow]'] |  |
| read_sql_query params (named → client-side format) | PASS | WHERE region = 'EU' pruned read → 1 row |  |
| read_sql_query params (qmark → server-side ExecutionParameters) | PASS | 52362edc-d5d6-490c-9ad3-eb24e34c118c bound server-side → 1 row; ExecutionParameters echoed=['EU'] |  |
| read_sql_table reads the full registered table | PASS | shape=(3, 3) |  |
| get_query_results fetches the csv artifact of a DML SELECT | PASS | 220ccbc1… → shape=(1, 2) |  |
| get_query_results fetches manifest parquet of a CTAS execution | PASS | cbe7ece2… → shape=(1, 2) |  |
| list_query_executions returns the workgroup's execution ids | PASS | 47 id(s) incl. 220ccbc1… |  |
| get_query_executions batch_gets into frames (+ unprocessed ids) | PASS | 2 execution rows + 1 unprocessed |  |
| get_query_execution returns the execution member | PASS | 220ccbc1… Status.State=SUCCEEDED |  |
| wait_query returns on a terminal execution | PASS | 220ccbc1… returned SUCCEEDED |  |
| describe_table returns the table's column listing | PASS | columns=['id', 'name', 'score'] |  |
| show_create_table returns the CREATE TABLE statement | PASS | CREATE TABLE hive.nb02_c2354a15.nb02_people_c2354a15 ( |  |
| get_query_columns_types maps ColumnInfo Name/Type | PASS | {'seven': 'integer', 'label': 'varchar(6)'} |  |
| get_query_columns_types formats decimal precision/scale | PASS | {'amount': 'decimal(6, 2)'} |  |
| create_athena_bucket creates the default results bucket | PASS | s3://aws-athena-query-results-123456789012-us-east-1/ exists on moto |  |
| get_work_group returns primary's configuration | PASS | state=ENABLED enforce=False |  |
