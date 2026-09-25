## 04_wrangler_read_paths

| feature | status | detail | latency_ms |
|---|---|---|---|
| wr.s3.to_parquet(dataset=True) registers Glue tables incl. partitions | PASS | nb04_people_cfaca8f8: 3 columns registered; nb04_sales_cfaca8f8: 2 partitions ['EU', 'US'] |  |
| read_sql_query csv path reads a wrangler-registered table | PASS | f057e0ba-587b-4792-8718-e1314c8059a2 shape=(3, 3) — Trino resolved the Glue-registered parquet table | 1155 |
| read_sql_query ctas_approach (temp CTAS → manifest → parquet read) | PASS | 8f2825ad-cd66-4483-96c2-da00777da6ad rows=1; manifest=8f2825ad-cd66-4483-96c2-da00777da6ad-manifest.csv | 1305 |
| read_sql_query api path (managed workgroup → inline GetQueryResults) | PASS | 2ad0db7b-18a4-42e6-9dd0-235fabf0a198 ResultConfiguration={}; 1 row(s) served inline | 122 |
| athena_cache_settings cache hit reuses the first execution | PASS | both reads → 2952caa5-cf08-4e57-be70-f37581b06d91; list+batch_get supplied the hit |  |
| read_sql_query categories → pandas Categorical | PASS | region dtype=category |  |
| read_sql_query chunksize=2 → iterator of row-bounded frames | PASS | chunk row counts=[2, 1] |  |
| read_sql_query dtype_backend="pyarrow" | PASS | dtypes=['int32[pyarrow]', 'double[pyarrow]'] |  |
| read_sql_query params (named → client-side format) | PASS | WHERE region = 'EU' pruned read → 1 row |  |
| read_sql_query params (qmark → server-side ExecutionParameters) | PASS | bc7ccdd0-cacd-422a-9843-62ef201dfc5a bound server-side → 1 row; ExecutionParameters echoed=['EU'] |  |
| read_sql_table reads the full registered table | PASS | shape=(3, 3) |  |
| get_query_results fetches the csv artifact of a DML SELECT | PASS | 2952caa5… → shape=(1, 2) |  |
| get_query_results fetches manifest parquet of a CTAS execution | PASS | 8f2825ad… → shape=(1, 2) |  |
| list_query_executions returns the workgroup's execution ids | PASS | 50 id(s) incl. 2952caa5… |  |
| get_query_executions batch_gets into frames (+ unprocessed ids) | PASS | 2 execution rows + 1 unprocessed |  |
| get_query_execution returns the execution member | PASS | 2952caa5… Status.State=SUCCEEDED |  |
| wait_query returns on a terminal execution | PASS | 2952caa5… returned SUCCEEDED |  |
| describe_table returns the table's column listing | GAP | InvalidRequestException (400): Exception parsing query: line 1:10: backquoted identifiers are not supported; us |  |
| show_create_table returns the CREATE TABLE statement | GAP | InvalidRequestException (400): Exception parsing query: line 1:19: backquoted identifiers are not supported; us |  |
| get_query_columns_types maps ColumnInfo Name/Type | PASS | {'seven': 'integer', 'label': 'varchar(6)'} |  |
| get_query_columns_types formats decimal precision/scale | PASS | {'amount': 'decimal(6, 2)'} |  |
| create_athena_bucket creates the default results bucket | PASS | s3://aws-athena-query-results-123456789012-us-east-1/ exists on moto |  |
| get_work_group returns primary's configuration | PASS | state=ENABLED enforce=False |  |
| read_sql_query unload_approach=True (UNLOAD → parquet read) | GAP | InvalidArgumentValue: Exception parsing query. Root error message: An error occurred (InvalidRequestEx |  |
| wr.athena.unload() writes a result set to S3 via UNLOAD | GAP | InvalidArgumentValue: Exception parsing query. Root error message: An error occurred (InvalidRequestEx |  |
| repair_table (MSCK REPAIR TABLE) discovers new partitions | GAP | InvalidRequestException (400): Exception parsing query: line 1:1: mismatched input 'MSCK'. Expecting: 'ALTER',  |  |
| SHOW PARTITIONS <table> (Athena spelling) | GAP | InvalidRequestException (400): Exception parsing query: line 1:6: mismatched input 'PARTITIONS'. Expecting: 'BR |  |
| "<table>$partitions" virtual table lists Glue partitions | PASS | Glue partitions=['EU', 'US'] |  |
