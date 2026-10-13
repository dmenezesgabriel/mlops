## 03_data_engineering

| feature | status | detail | latency_ms |
|---|---|---|---|
| wr.s3.to_parquet(dataset=True) registers tables + partitions | PASS | nb03_orders_cd4bd939 + nb03_sales_cd4bd939 registered; sales partitions=[['EU'], ['US']] |  |
| wr.athena.create_ctas_table (named CTAS → Glue table + parquet) | PASS | aa0875c1-e37d-4244-83e5-b1bb76ca47fc read back (2, 3); 1 object(s) at external_location; manifest=aa0875c1-e37d-4244-83e5-b1bb76ca47fc-manifest.csv | 2307.52 |
| SSE_KMS EncryptionConfiguration on CTAS | PASS | EncryptionConfiguration={'EncryptionOption': 'SSE_KMS', 'KmsKey': 'arn:aws:kms:us-east-1:123456789012:key/00000000-0000-0000-0000-000000000000'} |  |
| wr.s3.to_parquet SSE-KMS write headers | PASS | objects=['kms/orders.parquet'] |  |
| generate_create_query emits CREATE EXTERNAL TABLE DDL | PASS | 562 chars; external=True partitioned=True |  |
| CREATE EXTERNAL TABLE via StartQueryExecution (Athena DDL) | PASS | 2c40b395-4590-4040-a66a-70a19f1efe1c SUCCEEDED; nb03_ext_cd4bd939 registered EXTERNAL_TABLE |  |
| ALTER TABLE … ADD PARTITION (Athena DDL) | PASS | b61aeea7-1a75-4d28-87c2-ea458cf45593 SUCCEEDED; Glue partitions=[['EU']]; read back (2, 2) |  |
| repair_table (MSCK REPAIR TABLE) discovers new partitions | PASS | final state SUCCEEDED |  |
| SHOW PARTITIONS <table> (Athena spelling) | PASS | 6e3a9106-3b7e-47ba-bfd7-a368b8ada1d7 → partitions ['EU', 'XX'] |  |
| "<table>$partitions" virtual table lists Glue partitions | PASS | Glue partitions=['EU', 'XX'] |  |
| wr.catalog.add_parquet_partitions registers a staged partition | PASS | 3 partitions after add: [['EU'], ['US'], ['AP']] |  |
| wr.catalog.delete_partitions unregisters a partition | PASS | 2 partitions after delete: [['EU'], ['US']] |  |
| wr.s3.store_parquet_metadata registers inferred schema + partitions | PASS | nb03_meta_cd4bd939 columns=['amount', 'quantity'] partition_types={'region': 'string'} values=[['EU'], ['US']] |  |
| read_sql_query unload_approach=True (UNLOAD → parquet read) | PASS | shape=(2, 3) |  |
| wr.athena.unload() writes a result set to S3 via UNLOAD | PASS | 3 object(s) incl. manifest under s3://nb03-e3887373d0c0/export/ |  |
| wr.s3.delete_objects removes a staged prefix | PASS | s3://nb03-e3887373d0c0/meta/sales/ emptied |  |
| wr.catalog.delete_all_partitions empties the registry | PASS | nb03_meta_cd4bd939 has 0 partitions |  |
| wr.catalog.delete_table_if_exists drops the table | PASS | nb03_meta_cd4bd939 absent from the catalog |  |
| wr.catalog.delete_database removes an empty database | PASS | nb03_scratch_cd4bd939 absent from get_databases |  |
