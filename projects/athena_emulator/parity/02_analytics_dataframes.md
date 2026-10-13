## 02_analytics_dataframes

| feature | status | detail | latency_ms |
|---|---|---|---|
| read_sql_query csv path reads a wrangler-registered table | PASS | 7284d071-fec0-4c1b-bc6b-c2ceed20fea8 shape=(3, 3) — Trino resolved the Glue-registered parquet table | 2252.18 |
| read_sql_query ctas_approach (temp CTAS → manifest → parquet read) | PASS | dcd1279c-699f-4142-8635-7524ca641b45 rows=1; manifest=dcd1279c-699f-4142-8635-7524ca641b45-manifest.csv | 2307.59 |
| read_sql_query api path (managed workgroup → inline GetQueryResults) | PASS | 5c94a550-83c3-4b69-b1bf-a4d6b2b97fe7 ResultConfiguration={}; 1 row(s) served inline | 1295.68 |
| athena_cache_settings cache hit reuses the first execution | PASS | both reads → fb07302a-0bf4-4400-902f-1f1dfe5fb4f5; list+batch_get supplied the hit |  |
| read_sql_query categories → pandas Categorical | PASS | region dtype=category |  |
| read_sql_query chunksize=2 → iterator of row-bounded frames | PASS | chunk row counts=[2, 1] |  |
| read_sql_query dtype_backend="pyarrow" | PASS | dtypes=['int32[pyarrow]', 'double[pyarrow]'] |  |
| read_sql_query params (named → client-side format) | PASS | WHERE region = 'EU' pruned read → 1 row |  |
| read_sql_query params (qmark → server-side ExecutionParameters) | PASS | 657d9233-6f64-46f2-998c-28b002b845c8 bound server-side → 1 row; ExecutionParameters echoed=['EU'] |  |
| read_sql_table reads the full registered table | PASS | shape=(3, 3) |  |
| get_query_results fetches the csv artifact of a DML SELECT | PASS | fb07302a… → shape=(1, 2) |  |
| get_query_results fetches manifest parquet of a CTAS execution | PASS | dcd1279c… → shape=(1, 2) |  |
| list_query_executions returns the workgroup's execution ids | PASS | 17 id(s) incl. fb07302a… |  |
| get_query_executions batch_gets into frames (+ unprocessed ids) | PASS | 2 execution rows + 1 unprocessed |  |
| get_query_execution returns the execution member | PASS | fb07302a… Status.State=SUCCEEDED |  |
| wait_query returns on a terminal execution | PASS | fb07302a… returned SUCCEEDED |  |
| describe_table returns the table's column listing | PASS | columns=['id', 'name', 'score'] |  |
| show_create_table returns the CREATE TABLE statement | PASS | CREATE TABLE hive.nb02_48992d8f.nb02_people_48992d8f ( |  |
| get_query_columns_types maps ColumnInfo Name/Type | PASS | {'seven': 'integer', 'label': 'varchar(6)'} |  |
| get_query_columns_types formats decimal precision/scale | PASS | {'amount': 'decimal(6, 2)'} |  |
| create_athena_bucket creates the default results bucket | PASS | s3://aws-athena-query-results-123456789012-us-east-1/ exists on moto |  |
| get_work_group returns primary's configuration | PASS | state=ENABLED enforce=False |  |
