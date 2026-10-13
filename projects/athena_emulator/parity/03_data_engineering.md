## 03_data_engineering

| feature | status | detail | latency_ms |
|---|---|---|---|
| wr.s3.to_parquet(dataset=True) registers tables + partitions | PASS | nb03_orders_0c5003e8 + nb03_sales_0c5003e8 registered; sales partitions=[['EU'], ['US']] |  |
| wr.athena.create_ctas_table (named CTAS → Glue table + parquet) | PASS | 774a7d09-4fb7-4a58-92f6-458850eac5c4 read back (2, 3); 1 object(s) at external_location; manifest=774a7d09-4fb7-4a58-92f6-458850eac5c4-manifest.csv | 2127.71 |
| SSE_KMS EncryptionConfiguration on CTAS | PASS | EncryptionConfiguration={'EncryptionOption': 'SSE_KMS', 'KmsKey': 'arn:aws:kms:us-east-1:123456789012:key/00000000-0000-0000-0000-000000000000'} |  |
| wr.s3.to_parquet SSE-KMS write headers | PASS | objects=['kms/orders.parquet'] |  |
| generate_create_query emits CREATE EXTERNAL TABLE DDL | PASS | 562 chars; external=True partitioned=True |  |
| CREATE EXTERNAL TABLE via StartQueryExecution (Athena DDL) | PASS | 12181021-d323-4375-8566-ee6981571e44 SUCCEEDED; nb03_ext_0c5003e8 registered EXTERNAL_TABLE |  |
| ALTER TABLE … ADD PARTITION (Athena DDL) | PASS | fd7cb35a-e143-4407-bda4-61329a856dc1 SUCCEEDED; Glue partitions=[['EU']]; read back (2, 2) |  |
| repair_table (MSCK REPAIR TABLE) discovers new partitions | PASS | final state SUCCEEDED |  |
| SHOW PARTITIONS <table> (Athena spelling) | PASS | 82979d27-eb47-4d7e-8cf8-f85029133591 → partitions ['EU', 'XX'] |  |
| "<table>$partitions" virtual table lists Glue partitions | PASS | Glue partitions=['EU', 'XX'] |  |
| wr.catalog.add_parquet_partitions registers a staged partition | PASS | 3 partitions after add: [['EU'], ['US'], ['AP']] |  |
| wr.catalog.delete_partitions unregisters a partition | PASS | 2 partitions after delete: [['EU'], ['US']] |  |
| wr.s3.store_parquet_metadata registers inferred schema + partitions | PASS | nb03_meta_0c5003e8 columns=['amount', 'quantity'] partition_types={'region': 'string'} values=[['EU'], ['US']] |  |
| read_sql_query unload_approach=True (UNLOAD → parquet read) | PASS | shape=(2, 3) |  |
| wr.athena.unload() writes a result set to S3 via UNLOAD | PASS | 3 object(s) incl. manifest under s3://nb03-6c17c08383de/export/ |  |
| wr.s3.delete_objects removes a staged prefix | PASS | s3://nb03-6c17c08383de/meta/sales/ emptied |  |
| wr.catalog.delete_all_partitions empties the registry | PASS | nb03_meta_0c5003e8 has 0 partitions |  |
| wr.catalog.delete_table_if_exists drops the table | PASS | nb03_meta_0c5003e8 absent from the catalog |  |
| wr.catalog.delete_database removes an empty database | PASS | nb03_scratch_0c5003e8 absent from get_databases |  |
