## 02_analytics_dataframes

| feature | status | detail | latency_ms |
|---|---|---|---|
| read_sql_query csv path reads a wrangler-registered table | PASS | b1385ad7-36df-49bd-b3ed-89ae237fe5de shape=(3, 3) — Trino resolved the Glue-registered parquet table | 3216.71 |
| read_sql_query ctas_approach (temp CTAS → manifest → parquet read) | PASS | d3396a48-c02c-4ade-b756-c0a02873b3da rows=1; manifest=d3396a48-c02c-4ade-b756-c0a02873b3da-manifest.csv | 3315.34 |
| read_sql_query api path (managed workgroup → inline GetQueryResults) | PASS | d5a2973f-f03e-410e-88d8-0ad8caa4ac68 ResultConfiguration={}; 1 row(s) served inline | 1197.58 |
| athena_cache_settings cache hit reuses the first execution | PASS | both reads → 0fcd2d4e-6816-47d4-8df1-a7facf53a951; list+batch_get supplied the hit |  |
| read_sql_query categories → pandas Categorical | PASS | region dtype=category |  |
| read_sql_query chunksize=2 → iterator of row-bounded frames | PASS | chunk row counts=[2, 1] |  |
| read_sql_query dtype_backend="pyarrow" | PASS | dtypes=['int32[pyarrow]', 'double[pyarrow]'] |  |
| read_sql_query params (named → client-side format) | PASS | WHERE region = 'EU' pruned read → 1 row |  |
| read_sql_query params (qmark → server-side ExecutionParameters) | PASS | 7d286519-ae32-4985-aa96-e1af5abd8942 bound server-side → 1 row; ExecutionParameters echoed=['EU'] |  |
| read_sql_table reads the full registered table | PASS | shape=(3, 3) |  |
| get_query_results fetches the csv artifact of a DML SELECT | PASS | 0fcd2d4e… → shape=(1, 2) |  |
| get_query_results fetches manifest parquet of a CTAS execution | PASS | d3396a48… → shape=(1, 2) |  |
| list_query_executions returns the workgroup's execution ids | PASS | 11 id(s) incl. 0fcd2d4e… |  |
| get_query_executions batch_gets into frames (+ unprocessed ids) | PASS | 2 execution rows + 1 unprocessed |  |
| get_query_execution returns the execution member | PASS | 0fcd2d4e… Status.State=SUCCEEDED |  |
| wait_query returns on a terminal execution | PASS | 0fcd2d4e… returned SUCCEEDED |  |
| describe_table returns the table's column listing | PASS | columns=['id', 'name', 'score'] |  |
| show_create_table returns the CREATE TABLE statement | PASS | CREATE TABLE hive.nb02_183c2acf.nb02_people_183c2acf ( |  |
| get_query_columns_types maps ColumnInfo Name/Type | PASS | {'seven': 'integer', 'label': 'varchar(6)'} |  |
| get_query_columns_types formats decimal precision/scale | PASS | {'amount': 'decimal(6, 2)'} |  |
| create_athena_bucket creates the default results bucket | PASS | s3://aws-athena-query-results-123456789012-us-east-1/ exists on moto |  |
| get_work_group returns primary's configuration | PASS | state=ENABLED enforce=False |  |
