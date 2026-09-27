## 04_wrangler_read_paths

| feature | status | detail | latency_ms |
|---|---|---|---|
| wr.s3.to_parquet(dataset=True) registers Glue tables incl. partitions | PASS | nb04_people_f136d518: 3 columns registered; nb04_sales_f136d518: 2 partitions ['EU', 'US'] |  |
| read_sql_query csv path reads a wrangler-registered table | PASS | bab134c9-81b7-4893-9c7d-1beebbb2d763 shape=(3, 3) — Trino resolved the Glue-registered parquet table | 1117 |
| read_sql_query ctas_approach (temp CTAS → manifest → parquet read) | PASS | aaa2b164-e4e5-4c39-8a1d-135041022ed6 rows=1; manifest=aaa2b164-e4e5-4c39-8a1d-135041022ed6-manifest.csv | 1271 |
| read_sql_query api path (managed workgroup → inline GetQueryResults) | PASS | 4717cb66-5f67-401a-96c6-18773e111cab ResultConfiguration={}; 1 row(s) served inline | 1117 |
| athena_cache_settings cache hit reuses the first execution | PASS | both reads → 15ba709d-e05d-4a45-b7cc-14de3f46548a; list+batch_get supplied the hit |  |
| read_sql_query categories → pandas Categorical | PASS | region dtype=category |  |
| read_sql_query chunksize=2 → iterator of row-bounded frames | PASS | chunk row counts=[2, 1] |  |
| read_sql_query dtype_backend="pyarrow" | PASS | dtypes=['int32[pyarrow]', 'double[pyarrow]'] |  |
| read_sql_query params (named → client-side format) | PASS | WHERE region = 'EU' pruned read → 1 row |  |
| read_sql_query params (qmark → server-side ExecutionParameters) | PASS | f9ee2514-ca57-412c-b939-6b5641b4d4ba bound server-side → 1 row; ExecutionParameters echoed=['EU'] |  |
| read_sql_table reads the full registered table | PASS | shape=(3, 3) |  |
| get_query_results fetches the csv artifact of a DML SELECT | PASS | 15ba709d… → shape=(1, 2) |  |
| get_query_results fetches manifest parquet of a CTAS execution | PASS | aaa2b164… → shape=(1, 2) |  |
| list_query_executions returns the workgroup's execution ids | PASS | 23 id(s) incl. 15ba709d… |  |
| get_query_executions batch_gets into frames (+ unprocessed ids) | PASS | 2 execution rows + 1 unprocessed |  |
| get_query_execution returns the execution member | PASS | 15ba709d… Status.State=SUCCEEDED |  |
| wait_query returns on a terminal execution | PASS | 15ba709d… returned SUCCEEDED |  |
| describe_table returns the table's column listing | PASS | columns=['id', 'name', 'score'] |  |
| show_create_table returns the CREATE TABLE statement | PASS | CREATE TABLE hive.nb04_f136d518.nb04_people_f136d518 ( |  |
| get_query_columns_types maps ColumnInfo Name/Type | PASS | {'seven': 'integer', 'label': 'varchar(6)'} |  |
| get_query_columns_types formats decimal precision/scale | PASS | {'amount': 'decimal(6, 2)'} |  |
| create_athena_bucket creates the default results bucket | PASS | s3://aws-athena-query-results-123456789012-us-east-1/ exists on moto |  |
| get_work_group returns primary's configuration | PASS | state=ENABLED enforce=False |  |
| read_sql_query unload_approach=True (UNLOAD → parquet read) | PASS | shape=(1, 2) |  |
| wr.athena.unload() writes a result set to S3 via UNLOAD | PASS | unloaded under s3://nb04-cac173a231f7/unload/ |  |
| repair_table (MSCK REPAIR TABLE) discovers new partitions | PASS | final state SUCCEEDED |  |
| SHOW PARTITIONS <table> (Athena spelling) | PASS | rows=0 |  |
| "<table>$partitions" virtual table lists Glue partitions | PASS | Glue partitions=['EU', 'US', 'XX'] |  |
