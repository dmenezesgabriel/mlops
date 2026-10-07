## 04_wrangler_read_paths

| feature | status | detail | latency_ms |
|---|---|---|---|
| wr.s3.to_parquet(dataset=True) registers Glue tables incl. partitions | PASS | nb04_people_d6d560b4: 3 columns registered; nb04_sales_d6d560b4: 2 partitions ['EU', 'US'] |  |
| read_sql_query csv path reads a wrangler-registered table | PASS | 0332c9d4-ed88-4b0a-9fd2-0d8855cebce9 shape=(3, 3) — Trino resolved the Glue-registered parquet table | 1202.97 |
| read_sql_query ctas_approach (temp CTAS → manifest → parquet read) | PASS | a6617e6f-b876-449d-bb8a-abf3c6a0c5d4 rows=1; manifest=a6617e6f-b876-449d-bb8a-abf3c6a0c5d4-manifest.csv | 1156.98 |
| read_sql_query api path (managed workgroup → inline GetQueryResults) | PASS | 965f69ce-c2a2-4d20-b277-a17e5acdea46 ResultConfiguration={}; 1 row(s) served inline | 1129.02 |
| athena_cache_settings cache hit reuses the first execution | PASS | both reads → 29a52c83-a397-422b-af9d-43bc28e649f2; list+batch_get supplied the hit |  |
| read_sql_query categories → pandas Categorical | PASS | region dtype=category |  |
| read_sql_query chunksize=2 → iterator of row-bounded frames | PASS | chunk row counts=[2, 1] |  |
| read_sql_query dtype_backend="pyarrow" | PASS | dtypes=['int32[pyarrow]', 'double[pyarrow]'] |  |
| read_sql_query params (named → client-side format) | PASS | WHERE region = 'EU' pruned read → 1 row |  |
| read_sql_query params (qmark → server-side ExecutionParameters) | PASS | bc2d62e2-e602-47a5-bb78-29b362a9d851 bound server-side → 1 row; ExecutionParameters echoed=['EU'] |  |
| read_sql_table reads the full registered table | PASS | shape=(3, 3) |  |
| get_query_results fetches the csv artifact of a DML SELECT | PASS | 29a52c83… → shape=(1, 2) |  |
| get_query_results fetches manifest parquet of a CTAS execution | PASS | a6617e6f… → shape=(1, 2) |  |
| list_query_executions returns the workgroup's execution ids | PASS | 362 id(s) incl. 29a52c83… |  |
| get_query_executions batch_gets into frames (+ unprocessed ids) | PASS | 2 execution rows + 1 unprocessed |  |
| get_query_execution returns the execution member | PASS | 29a52c83… Status.State=SUCCEEDED |  |
| wait_query returns on a terminal execution | PASS | 29a52c83… returned SUCCEEDED |  |
| describe_table returns the table's column listing | PASS | columns=['id', 'name', 'score'] |  |
| show_create_table returns the CREATE TABLE statement | PASS | CREATE TABLE hive.nb04_d6d560b4.nb04_people_d6d560b4 ( |  |
| get_query_columns_types maps ColumnInfo Name/Type | PASS | {'seven': 'integer', 'label': 'varchar(6)'} |  |
| get_query_columns_types formats decimal precision/scale | PASS | {'amount': 'decimal(6, 2)'} |  |
| create_athena_bucket creates the default results bucket | PASS | s3://aws-athena-query-results-123456789012-us-east-1/ exists on moto |  |
| get_work_group returns primary's configuration | PASS | state=ENABLED enforce=False |  |
| read_sql_query unload_approach=True (UNLOAD → parquet read) | PASS | shape=(1, 2) |  |
| wr.athena.unload() writes a result set to S3 via UNLOAD | PASS | unloaded under s3://nb04-49af1f2fcdfa/unload/ |  |
| repair_table (MSCK REPAIR TABLE) discovers new partitions | PASS | final state SUCCEEDED |  |
| SHOW PARTITIONS <table> (Athena spelling) | PASS | rows=0 |  |
| "<table>$partitions" virtual table lists Glue partitions | PASS | Glue partitions=['EU', 'US', 'XX'] |  |
