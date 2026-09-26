## 04_wrangler_read_paths

| feature | status | detail | latency_ms |
|---|---|---|---|
| wr.s3.to_parquet(dataset=True) registers Glue tables incl. partitions | PASS | nb04_people_5e9a1384: 3 columns registered; nb04_sales_5e9a1384: 2 partitions ['EU', 'US'] |  |
| read_sql_query csv path reads a wrangler-registered table | PASS | 566f1c06-f589-4906-bfa4-6f74b140f422 shape=(3, 3) — Trino resolved the Glue-registered parquet table | 1066 |
| read_sql_query ctas_approach (temp CTAS → manifest → parquet read) | PASS | c9b6399b-16f6-4ec9-94e7-ff19840cca35 rows=1; manifest=c9b6399b-16f6-4ec9-94e7-ff19840cca35-manifest.csv | 1149 |
| read_sql_query api path (managed workgroup → inline GetQueryResults) | PASS | 76e6b670-a8e2-4fee-ada1-a4479280ccfb ResultConfiguration={}; 1 row(s) served inline | 1067 |
| athena_cache_settings cache hit reuses the first execution | PASS | both reads → 3a8969e1-1bc6-46be-a312-f62a9a329217; list+batch_get supplied the hit |  |
| read_sql_query categories → pandas Categorical | PASS | region dtype=category |  |
| read_sql_query chunksize=2 → iterator of row-bounded frames | PASS | chunk row counts=[2, 1] |  |
| read_sql_query dtype_backend="pyarrow" | PASS | dtypes=['int32[pyarrow]', 'double[pyarrow]'] |  |
| read_sql_query params (named → client-side format) | PASS | WHERE region = 'EU' pruned read → 1 row |  |
| read_sql_query params (qmark → server-side ExecutionParameters) | PASS | 9654635c-eef5-4cc1-ab6c-cc314b05b81b bound server-side → 1 row; ExecutionParameters echoed=['EU'] |  |
| read_sql_table reads the full registered table | PASS | shape=(3, 3) |  |
| get_query_results fetches the csv artifact of a DML SELECT | PASS | 3a8969e1… → shape=(1, 2) |  |
| get_query_results fetches manifest parquet of a CTAS execution | PASS | c9b6399b… → shape=(1, 2) |  |
| list_query_executions returns the workgroup's execution ids | PASS | 12 id(s) incl. 3a8969e1… |  |
| get_query_executions batch_gets into frames (+ unprocessed ids) | PASS | 2 execution rows + 1 unprocessed |  |
| get_query_execution returns the execution member | PASS | 3a8969e1… Status.State=SUCCEEDED |  |
| wait_query returns on a terminal execution | PASS | 3a8969e1… returned SUCCEEDED |  |
| describe_table returns the table's column listing | PASS | columns=['id', 'name', 'score'] |  |
| show_create_table returns the CREATE TABLE statement | PASS | CREATE TABLE hive.nb04_5e9a1384.nb04_people_5e9a1384 ( |  |
| get_query_columns_types maps ColumnInfo Name/Type | PASS | {'seven': 'integer', 'label': 'varchar(6)'} |  |
| get_query_columns_types formats decimal precision/scale | PASS | {'amount': 'decimal(6, 2)'} |  |
| create_athena_bucket creates the default results bucket | PASS | s3://aws-athena-query-results-123456789012-us-east-1/ exists on moto |  |
| get_work_group returns primary's configuration | PASS | state=ENABLED enforce=False |  |
| read_sql_query unload_approach=True (UNLOAD → parquet read) | GAP | InvalidArgumentValue: Exception parsing query. Root error message: An error occurred (InvalidRequestEx |  |
| wr.athena.unload() writes a result set to S3 via UNLOAD | GAP | InvalidArgumentValue: Exception parsing query. Root error message: An error occurred (InvalidRequestEx |  |
| repair_table (MSCK REPAIR TABLE) discovers new partitions | PASS | final state SUCCEEDED |  |
| SHOW PARTITIONS <table> (Athena spelling) | GAP | InvalidRequestException (400): Exception parsing query: line 1:6: mismatched input 'PARTITIONS'. Expecting: 'BR |  |
| "<table>$partitions" virtual table lists Glue partitions | PASS | Glue partitions=['EU', 'US', 'XX'] |  |
