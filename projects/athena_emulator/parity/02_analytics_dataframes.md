## 02_analytics_dataframes

| feature | status | detail | latency_ms |
|---|---|---|---|
| read_sql_query csv path reads a wrangler-registered table | PASS | 02ffaeab-1e10-48e7-9c8a-2a7061aa6567 shape=(3, 3) — Trino resolved the Glue-registered parquet table | 1085.71 |
| read_sql_query ctas_approach (temp CTAS → manifest → parquet read) | PASS | c91dd96d-57b3-419a-9c7b-1a758e7b8959 rows=1; manifest=c91dd96d-57b3-419a-9c7b-1a758e7b8959-manifest.csv | 1101.57 |
| read_sql_query api path (managed workgroup → inline GetQueryResults) | PASS | a2ecd491-0eb4-498f-9508-9d173b4ce33e ResultConfiguration={}; 1 row(s) served inline | 1083.22 |
| athena_cache_settings cache hit reuses the first execution | PASS | both reads → a0acb8f0-7225-426d-8cc7-711009e628b9; list+batch_get supplied the hit |  |
| read_sql_query categories → pandas Categorical | PASS | region dtype=category |  |
| read_sql_query chunksize=2 → iterator of row-bounded frames | PASS | chunk row counts=[2, 1] |  |
| read_sql_query dtype_backend="pyarrow" | PASS | dtypes=['int32[pyarrow]', 'double[pyarrow]'] |  |
| read_sql_query params (named → client-side format) | PASS | WHERE region = 'EU' pruned read → 1 row |  |
| read_sql_query params (qmark → server-side ExecutionParameters) | PASS | 307ba069-6f6d-4226-b4b5-f8e42081329a bound server-side → 1 row; ExecutionParameters echoed=['EU'] |  |
| read_sql_table reads the full registered table | PASS | shape=(3, 3) |  |
| get_query_results fetches the csv artifact of a DML SELECT | PASS | a0acb8f0… → shape=(1, 2) |  |
| get_query_results fetches manifest parquet of a CTAS execution | PASS | c91dd96d… → shape=(1, 2) |  |
| list_query_executions returns the workgroup's execution ids | PASS | 15 id(s) incl. a0acb8f0… |  |
| get_query_executions batch_gets into frames (+ unprocessed ids) | PASS | 2 execution rows + 1 unprocessed |  |
| get_query_execution returns the execution member | PASS | a0acb8f0… Status.State=SUCCEEDED |  |
| wait_query returns on a terminal execution | PASS | a0acb8f0… returned SUCCEEDED |  |
| describe_table returns the table's column listing | PASS | columns=['id', 'name', 'score'] |  |
| show_create_table returns the CREATE TABLE statement | PASS | CREATE TABLE hive.nb02_b8c9af57.nb02_people_b8c9af57 ( |  |
| get_query_columns_types maps ColumnInfo Name/Type | PASS | {'seven': 'integer', 'label': 'varchar(6)'} |  |
| get_query_columns_types formats decimal precision/scale | PASS | {'amount': 'decimal(6, 2)'} |  |
| create_athena_bucket creates the default results bucket | PASS | s3://aws-athena-query-results-123456789012-us-east-1/ exists on moto |  |
| get_work_group returns primary's configuration | PASS | state=ENABLED enforce=False |  |
