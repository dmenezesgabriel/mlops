## 03_data_engineering

| feature | status | detail | latency_ms |
|---|---|---|---|
| wr.s3.to_parquet(dataset=True) registers tables + partitions | PASS | nb03_orders_1ac50cd6 + nb03_sales_1ac50cd6 registered; sales partitions=[['EU'], ['US']] |  |
| wr.athena.create_ctas_table (named CTAS → Glue table + parquet) | PASS | e689be8d-ffd9-4a4d-a12a-f8a6b4c2d8c0 read back (2, 3); 1 object(s) at external_location; manifest=e689be8d-ffd9-4a4d-a12a-f8a6b4c2d8c0-manifest.csv | 2510.06 |
| SSE_KMS EncryptionConfiguration on CTAS | PASS | EncryptionConfiguration={'EncryptionOption': 'SSE_KMS', 'KmsKey': 'arn:aws:kms:us-east-1:123456789012:key/00000000-0000-0000-0000-000000000000'} |  |
| wr.s3.to_parquet SSE-KMS write headers | PASS | objects=['kms/orders.parquet'] |  |
| generate_create_query emits CREATE EXTERNAL TABLE DDL | PASS | 562 chars; external=True partitioned=True |  |
| CREATE EXTERNAL TABLE via StartQueryExecution (Athena DDL) | PASS | f82163f4-8d1d-4d4d-ae4a-8416d68fa3dc SUCCEEDED; nb03_ext_1ac50cd6 registered EXTERNAL_TABLE |  |
| ALTER TABLE … ADD PARTITION (Athena DDL) | PASS | 9c6402ae-5ee7-4906-81b3-4f4b7944b894 SUCCEEDED; Glue partitions=[['EU']]; read back (2, 2) |  |
| repair_table (MSCK REPAIR TABLE) discovers new partitions | PASS | final state SUCCEEDED |  |
| SHOW PARTITIONS <table> (Athena spelling) | PASS | c6f5f7dc-68ab-4c5a-ab6a-865f4b00df29 → partitions ['EU', 'XX'] |  |
| "<table>$partitions" virtual table lists Glue partitions | PASS | Glue partitions=['EU', 'XX'] |  |
| wr.catalog.add_parquet_partitions registers a staged partition | PASS | 3 partitions after add: [['EU'], ['US'], ['AP']] |  |
| wr.catalog.delete_partitions unregisters a partition | PASS | 2 partitions after delete: [['EU'], ['US']] |  |
| wr.s3.store_parquet_metadata registers inferred schema + partitions | PASS | nb03_meta_1ac50cd6 columns=['amount', 'quantity'] partition_types={'region': 'string'} values=[['EU'], ['US']] |  |
| read_sql_query unload_approach=True (UNLOAD → parquet read) | PASS | shape=(2, 3) |  |
| wr.athena.unload() writes a result set to S3 via UNLOAD | PASS | 3 object(s) incl. manifest under s3://nb03-23071d71cf9a/export/ |  |
| wr.s3.delete_objects removes a staged prefix | PASS | s3://nb03-23071d71cf9a/meta/sales/ emptied |  |
| wr.catalog.delete_all_partitions empties the registry | PASS | nb03_meta_1ac50cd6 has 0 partitions |  |
| wr.catalog.delete_table_if_exists drops the table | PASS | nb03_meta_1ac50cd6 absent from the catalog |  |
| wr.catalog.delete_database removes an empty database | PASS | nb03_scratch_1ac50cd6 absent from get_databases |  |
