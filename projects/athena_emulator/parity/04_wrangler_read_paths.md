## 04_wrangler_read_paths

| feature | status | detail | latency_ms |
|---|---|---|---|
| wr.s3.to_parquet(dataset=True) registers Glue tables incl. partitions | PASS | nb04_people_fb6815ea: 3 columns registered; nb04_sales_fb6815ea: 2 partitions ['EU', 'US'] |  |
| read_sql_query csv path reads a wrangler-registered table | PASS | 65461ad0-452f-4082-864e-1039c086ebf7 shape=(3, 3) — Trino resolved the Glue-registered parquet table | 1125 |
| read_sql_query ctas_approach (temp CTAS → manifest → parquet read) | PASS | 423a367f-ca36-4205-bd86-b05365c5d54c rows=1; manifest=423a367f-ca36-4205-bd86-b05365c5d54c-manifest.csv | 1242 |
| read_sql_query api path (managed workgroup → inline GetQueryResults) | PASS | 2152ad2d-e6b0-4e53-8434-8e993dfcc3ea ResultConfiguration={}; 1 row(s) served inline | 1147 |
| athena_cache_settings cache hit reuses the first execution | PASS | both reads → 69bce35f-f27a-4eb5-94a5-65b3a582ccea; list+batch_get supplied the hit |  |
| read_sql_query categories → pandas Categorical | PASS | region dtype=category |  |
| read_sql_query chunksize=2 → iterator of row-bounded frames | PASS | chunk row counts=[2, 1] |  |
| read_sql_query dtype_backend="pyarrow" | PASS | dtypes=['int32[pyarrow]', 'double[pyarrow]'] |  |
| read_sql_query params (named → client-side format) | PASS | WHERE region = 'EU' pruned read → 1 row |  |
| read_sql_query params (qmark → server-side ExecutionParameters) | PASS | 84ed47f4-4d75-4eb0-a805-4ea7ddfad47b bound server-side → 1 row; ExecutionParameters echoed=['EU'] |  |
| read_sql_table reads the full registered table | PASS | shape=(3, 3) |  |
| get_query_results fetches the csv artifact of a DML SELECT | PASS | 69bce35f… → shape=(1, 2) |  |
| get_query_results fetches manifest parquet of a CTAS execution | PASS | 423a367f… → shape=(1, 2) |  |
| list_query_executions returns the workgroup's execution ids | PASS | 10 id(s) incl. 69bce35f… |  |
| get_query_executions batch_gets into frames (+ unprocessed ids) | PASS | 2 execution rows + 1 unprocessed |  |
| get_query_execution returns the execution member | PASS | 69bce35f… Status.State=SUCCEEDED |  |
| wait_query returns on a terminal execution | PASS | 69bce35f… returned SUCCEEDED |  |
| describe_table returns the table's column listing | PASS | columns=['id', 'name', 'score'] |  |
| show_create_table returns the CREATE TABLE statement | PASS | CREATE TABLE hive.nb04_fb6815ea.nb04_people_fb6815ea ( |  |
| get_query_columns_types maps ColumnInfo Name/Type | PASS | {'seven': 'integer', 'label': 'varchar(6)'} |  |
| get_query_columns_types formats decimal precision/scale | PASS | {'amount': 'decimal(6, 2)'} |  |
| create_athena_bucket creates the default results bucket | PASS | s3://aws-athena-query-results-123456789012-us-east-1/ exists on moto |  |
| get_work_group returns primary's configuration | PASS | state=ENABLED enforce=False |  |
| read_sql_query unload_approach=True (UNLOAD → parquet read) | GAP | InvalidArgumentValue: Exception parsing query. Root error message: An error occurred (InvalidRequestEx |  |
| wr.athena.unload() writes a result set to S3 via UNLOAD | GAP | InvalidArgumentValue: Exception parsing query. Root error message: An error occurred (InvalidRequestEx |  |
| repair_table (MSCK REPAIR TABLE) discovers new partitions | GAP | InvalidRequestException (400): Exception parsing query: line 1:1: mismatched input 'MSCK'. Expecting: 'ALTER',  |  |
| SHOW PARTITIONS <table> (Athena spelling) | GAP | InvalidRequestException (400): Exception parsing query: line 1:6: mismatched input 'PARTITIONS'. Expecting: 'BR |  |
| "<table>$partitions" virtual table lists Glue partitions | PASS | Glue partitions=['EU', 'US'] |  |
