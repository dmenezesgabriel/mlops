## 04_wrangler_read_paths

| feature | status | detail | latency_ms |
|---|---|---|---|
| wr.s3.to_parquet(dataset=True) registers Glue tables incl. partitions | PASS | nb04_people_25ad67a7: 3 columns registered; nb04_sales_25ad67a7: 2 partitions ['EU', 'US'] |  |
| read_sql_query csv path reads a wrangler-registered table | PASS | c697c374-343e-4e2d-aed5-4b9294123758 shape=(3, 3) — Trino resolved the Glue-registered parquet table | 1068 |
| read_sql_query ctas_approach (temp CTAS → manifest → parquet read) | PASS | c60716af-2c33-4ce1-9e54-fd46e3a68dde rows=1; manifest=c60716af-2c33-4ce1-9e54-fd46e3a68dde-manifest.csv | 1155 |
| read_sql_query api path (managed workgroup → inline GetQueryResults) | PASS | 2886889f-0fae-41d7-8a03-5271bb52294c ResultConfiguration={}; 1 row(s) served inline | 1060 |
| athena_cache_settings cache hit reuses the first execution | PASS | both reads → 202c06df-2121-43a2-ae24-7b9b94c24afc; list+batch_get supplied the hit |  |
| read_sql_query categories → pandas Categorical | PASS | region dtype=category |  |
| read_sql_query chunksize=2 → iterator of row-bounded frames | PASS | chunk row counts=[2, 1] |  |
| read_sql_query dtype_backend="pyarrow" | PASS | dtypes=['int32[pyarrow]', 'double[pyarrow]'] |  |
| read_sql_query params (named → client-side format) | PASS | WHERE region = 'EU' pruned read → 1 row |  |
| read_sql_query params (qmark → server-side ExecutionParameters) | PASS | 8dc1bbdb-e616-4603-b24a-6f5179770b07 bound server-side → 1 row; ExecutionParameters echoed=['EU'] |  |
| read_sql_table reads the full registered table | PASS | shape=(3, 3) |  |
| get_query_results fetches the csv artifact of a DML SELECT | PASS | 202c06df… → shape=(1, 2) |  |
| get_query_results fetches manifest parquet of a CTAS execution | PASS | c60716af… → shape=(1, 2) |  |
| list_query_executions returns the workgroup's execution ids | PASS | 70 id(s) incl. 202c06df… |  |
| get_query_executions batch_gets into frames (+ unprocessed ids) | PASS | 2 execution rows + 1 unprocessed |  |
| get_query_execution returns the execution member | PASS | 202c06df… Status.State=SUCCEEDED |  |
| wait_query returns on a terminal execution | PASS | 202c06df… returned SUCCEEDED |  |
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
