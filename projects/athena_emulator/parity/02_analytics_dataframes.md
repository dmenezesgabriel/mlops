## 02_analytics_dataframes

| feature | status | detail | latency_ms |
|---|---|---|---|
| read_sql_query csv path reads a wrangler-registered table | PASS | 9f33fcb5-4e92-4143-880e-a468c9af1e7e shape=(3, 3) — Trino resolved the Glue-registered parquet table | 2235.18 |
| read_sql_query ctas_approach (temp CTAS → manifest → parquet read) | PASS | e40149be-f777-4712-bc29-c2f055b1fcf9 rows=1; manifest=e40149be-f777-4712-bc29-c2f055b1fcf9-manifest.csv | 2214.25 |
| read_sql_query api path (managed workgroup → inline GetQueryResults) | PASS | 092b55da-fb5d-489a-9a87-e51d246dcef8 ResultConfiguration={}; 1 row(s) served inline | 1131.36 |
| athena_cache_settings cache hit reuses the first execution | PASS | both reads → 53b45fe4-d1ad-46c4-be81-b1bc7918cc38; list+batch_get supplied the hit |  |
| read_sql_query categories → pandas Categorical | PASS | region dtype=category |  |
| read_sql_query chunksize=2 → iterator of row-bounded frames | PASS | chunk row counts=[2, 1] |  |
| read_sql_query dtype_backend="pyarrow" | PASS | dtypes=['int32[pyarrow]', 'double[pyarrow]'] |  |
| read_sql_query params (named → client-side format) | PASS | WHERE region = 'EU' pruned read → 1 row |  |
| read_sql_query params (qmark → server-side ExecutionParameters) | PASS | 52f5d23e-bbbf-431c-bfac-697354341e15 bound server-side → 1 row; ExecutionParameters echoed=['EU'] |  |
| read_sql_table reads the full registered table | PASS | shape=(3, 3) |  |
| get_query_results fetches the csv artifact of a DML SELECT | PASS | 53b45fe4… → shape=(1, 2) |  |
| get_query_results fetches manifest parquet of a CTAS execution | PASS | e40149be… → shape=(1, 2) |  |
| list_query_executions returns the workgroup's execution ids | PASS | 11 id(s) incl. 53b45fe4… |  |
| get_query_executions batch_gets into frames (+ unprocessed ids) | PASS | 2 execution rows + 1 unprocessed |  |
| get_query_execution returns the execution member | PASS | 53b45fe4… Status.State=SUCCEEDED |  |
| wait_query returns on a terminal execution | PASS | 53b45fe4… returned SUCCEEDED |  |
| describe_table returns the table's column listing | PASS | columns=['id', 'name', 'score'] |  |
| show_create_table returns the CREATE TABLE statement | PASS | CREATE TABLE hive.nb02_68e9875f.nb02_people_68e9875f ( |  |
| get_query_columns_types maps ColumnInfo Name/Type | PASS | {'seven': 'integer', 'label': 'varchar(6)'} |  |
| get_query_columns_types formats decimal precision/scale | PASS | {'amount': 'decimal(6, 2)'} |  |
| create_athena_bucket creates the default results bucket | PASS | s3://aws-athena-query-results-123456789012-us-east-1/ exists on moto |  |
| get_work_group returns primary's configuration | PASS | state=ENABLED enforce=False |  |
