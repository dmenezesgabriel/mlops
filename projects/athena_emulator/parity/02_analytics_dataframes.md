## 02_analytics_dataframes

| feature | status | detail | latency_ms |
|---|---|---|---|
| read_sql_query csv path reads a wrangler-registered table | PASS | 7a9b8eaf-2d0b-45cf-ad90-b1b2bb2a4f88 shape=(3, 3) — Trino resolved the Glue-registered parquet table | 1080.39 |
| read_sql_query ctas_approach (temp CTAS → manifest → parquet read) | PASS | 2fd571ee-0129-4145-8bba-85d4bfece95b rows=1; manifest=2fd571ee-0129-4145-8bba-85d4bfece95b-manifest.csv | 1080.44 |
| read_sql_query api path (managed workgroup → inline GetQueryResults) | PASS | fcc5266d-ad09-4979-aa2e-da35fab2be49 ResultConfiguration={}; 1 row(s) served inline | 1073.39 |
| athena_cache_settings cache hit reuses the first execution | PASS | both reads → ce5e69a6-d06c-4f43-8f6e-be46cd6cb8cd; list+batch_get supplied the hit |  |
| read_sql_query categories → pandas Categorical | PASS | region dtype=category |  |
| read_sql_query chunksize=2 → iterator of row-bounded frames | PASS | chunk row counts=[2, 1] |  |
| read_sql_query dtype_backend="pyarrow" | PASS | dtypes=['int32[pyarrow]', 'double[pyarrow]'] |  |
| read_sql_query params (named → client-side format) | PASS | WHERE region = 'EU' pruned read → 1 row |  |
| read_sql_query params (qmark → server-side ExecutionParameters) | PASS | 9b782883-7b4e-4d86-b173-c939e1d0f367 bound server-side → 1 row; ExecutionParameters echoed=['EU'] |  |
| read_sql_table reads the full registered table | PASS | shape=(3, 3) |  |
| get_query_results fetches the csv artifact of a DML SELECT | PASS | ce5e69a6… → shape=(1, 2) |  |
| get_query_results fetches manifest parquet of a CTAS execution | PASS | 2fd571ee… → shape=(1, 2) |  |
| list_query_executions returns the workgroup's execution ids | PASS | 11 id(s) incl. ce5e69a6… |  |
| get_query_executions batch_gets into frames (+ unprocessed ids) | PASS | 2 execution rows + 1 unprocessed |  |
| get_query_execution returns the execution member | PASS | ce5e69a6… Status.State=SUCCEEDED |  |
| wait_query returns on a terminal execution | PASS | ce5e69a6… returned SUCCEEDED |  |
| describe_table returns the table's column listing | PASS | columns=['id', 'name', 'score'] |  |
| show_create_table returns the CREATE TABLE statement | PASS | CREATE TABLE hive.nb02_857146fc.nb02_people_857146fc ( |  |
| get_query_columns_types maps ColumnInfo Name/Type | PASS | {'seven': 'integer', 'label': 'varchar(6)'} |  |
| get_query_columns_types formats decimal precision/scale | PASS | {'amount': 'decimal(6, 2)'} |  |
| create_athena_bucket creates the default results bucket | PASS | s3://aws-athena-query-results-123456789012-us-east-1/ exists on moto |  |
| get_work_group returns primary's configuration | PASS | state=ENABLED enforce=False |  |
