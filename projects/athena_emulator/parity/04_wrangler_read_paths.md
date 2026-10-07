## 04_wrangler_read_paths

| feature | status | detail | latency_ms |
|---|---|---|---|
| wr.s3.to_parquet(dataset=True) registers Glue tables incl. partitions | PASS | nb04_people_d83516b3: 3 columns registered; nb04_sales_d83516b3: 2 partitions ['EU', 'US'] |  |
| read_sql_query csv path reads a wrangler-registered table | PASS | c8d4a49e-24e2-4dc0-8880-b4649133d6e3 shape=(3, 3) — Trino resolved the Glue-registered parquet table | 1126.64 |
| read_sql_query ctas_approach (temp CTAS → manifest → parquet read) | PASS | f05a67cf-b0b7-420d-81dd-f57abdfff5c5 rows=1; manifest=f05a67cf-b0b7-420d-81dd-f57abdfff5c5-manifest.csv | 1160.48 |
| read_sql_query api path (managed workgroup → inline GetQueryResults) | PASS | 597da4c9-994a-49f5-9029-92844bbc224b ResultConfiguration={}; 1 row(s) served inline | 1106.67 |
| athena_cache_settings cache hit reuses the first execution | PASS | both reads → 3d4b6fd2-b766-4aa5-a44a-2f4aa9c8dbb6; list+batch_get supplied the hit |  |
| read_sql_query categories → pandas Categorical | PASS | region dtype=category |  |
| read_sql_query chunksize=2 → iterator of row-bounded frames | PASS | chunk row counts=[2, 1] |  |
| read_sql_query dtype_backend="pyarrow" | PASS | dtypes=['int32[pyarrow]', 'double[pyarrow]'] |  |
| read_sql_query params (named → client-side format) | PASS | WHERE region = 'EU' pruned read → 1 row |  |
| read_sql_query params (qmark → server-side ExecutionParameters) | PASS | 163500d4-dd09-49d6-bd99-43cdc56dc99e bound server-side → 1 row; ExecutionParameters echoed=['EU'] |  |
| read_sql_table reads the full registered table | PASS | shape=(3, 3) |  |
| get_query_results fetches the csv artifact of a DML SELECT | PASS | 3d4b6fd2… → shape=(1, 2) |  |
| get_query_results fetches manifest parquet of a CTAS execution | PASS | f05a67cf… → shape=(1, 2) |  |
| list_query_executions returns the workgroup's execution ids | PASS | 227 id(s) incl. 3d4b6fd2… |  |
| get_query_executions batch_gets into frames (+ unprocessed ids) | PASS | 2 execution rows + 1 unprocessed |  |
| get_query_execution returns the execution member | PASS | 3d4b6fd2… Status.State=SUCCEEDED |  |
| wait_query returns on a terminal execution | PASS | 3d4b6fd2… returned SUCCEEDED |  |
| describe_table returns the table's column listing | PASS | columns=['id', 'name', 'score'] |  |
| show_create_table returns the CREATE TABLE statement | PASS | CREATE TABLE hive.nb04_d83516b3.nb04_people_d83516b3 ( |  |
| get_query_columns_types maps ColumnInfo Name/Type | PASS | {'seven': 'integer', 'label': 'varchar(6)'} |  |
| get_query_columns_types formats decimal precision/scale | PASS | {'amount': 'decimal(6, 2)'} |  |
| create_athena_bucket creates the default results bucket | PASS | s3://aws-athena-query-results-123456789012-us-east-1/ exists on moto |  |
| get_work_group returns primary's configuration | PASS | state=ENABLED enforce=False |  |
| read_sql_query unload_approach=True (UNLOAD → parquet read) | PASS | shape=(1, 2) |  |
| wr.athena.unload() writes a result set to S3 via UNLOAD | PASS | unloaded under s3://nb04-46d5a44a1190/unload/ |  |
| repair_table (MSCK REPAIR TABLE) discovers new partitions | PASS | final state SUCCEEDED |  |
| SHOW PARTITIONS <table> (Athena spelling) | PASS | rows=0 |  |
| "<table>$partitions" virtual table lists Glue partitions | PASS | Glue partitions=['EU', 'US', 'XX'] |  |
