## 03_data_engineering

| feature | status | detail | latency_ms |
|---|---|---|---|
| wr.s3.to_parquet(dataset=True) registers tables + partitions | PASS | nb03_orders_6a03b22f + nb03_sales_6a03b22f registered; sales partitions=[['EU'], ['US']] |  |
| wr.athena.create_ctas_table (named CTAS → Glue table + parquet) | PASS | 23646d67-da54-4b25-bc1d-f55359c78eab read back (2, 3); 1 object(s) at external_location; manifest=23646d67-da54-4b25-bc1d-f55359c78eab-manifest.csv | 2248.69 |
| SSE_KMS EncryptionConfiguration on CTAS | PASS | EncryptionConfiguration={'EncryptionOption': 'SSE_KMS', 'KmsKey': 'arn:aws:kms:us-east-1:123456789012:key/00000000-0000-0000-0000-000000000000'} |  |
| wr.s3.to_parquet SSE-KMS write headers | PASS | objects=['kms/orders.parquet'] |  |
| generate_create_query emits CREATE EXTERNAL TABLE DDL | PASS | 562 chars; external=True partitioned=True |  |
| CREATE EXTERNAL TABLE via StartQueryExecution (Athena DDL) | PASS | c7d39724-bae9-4c6f-b329-7c50c9596fae SUCCEEDED; nb03_ext_6a03b22f registered EXTERNAL_TABLE |  |
| ALTER TABLE … ADD PARTITION (Athena DDL) | PASS | c2465b73-6173-4af2-bafe-a0a97774c0cf SUCCEEDED; Glue partitions=[['EU']]; read back (2, 2) |  |
| repair_table (MSCK REPAIR TABLE) discovers new partitions | PASS | final state SUCCEEDED |  |
| SHOW PARTITIONS <table> (Athena spelling) | PASS | 5334d0a4-0eaf-4dc7-8284-e46b292284eb → partitions ['EU', 'XX'] |  |
| "<table>$partitions" virtual table lists Glue partitions | PASS | Glue partitions=['EU', 'XX'] |  |
| wr.catalog.add_parquet_partitions registers a staged partition | PASS | 3 partitions after add: [['EU'], ['US'], ['AP']] |  |
| wr.catalog.delete_partitions unregisters a partition | PASS | 2 partitions after delete: [['EU'], ['US']] |  |
| wr.s3.store_parquet_metadata registers inferred schema + partitions | PASS | nb03_meta_6a03b22f columns=['amount', 'quantity'] partition_types={'region': 'string'} values=[['EU'], ['US']] |  |
| read_sql_query unload_approach=True (UNLOAD → parquet read) | PASS | shape=(2, 3) |  |
| wr.athena.unload() writes a result set to S3 via UNLOAD | PASS | 3 object(s) incl. manifest under s3://nb03-57f15e792ed7/export/ |  |
| wr.s3.delete_objects removes a staged prefix | PASS | s3://nb03-57f15e792ed7/meta/sales/ emptied |  |
| wr.catalog.delete_all_partitions empties the registry | PASS | nb03_meta_6a03b22f has 0 partitions |  |
| wr.catalog.delete_table_if_exists drops the table | PASS | nb03_meta_6a03b22f absent from the catalog |  |
| wr.catalog.delete_database removes an empty database | PASS | nb03_scratch_6a03b22f absent from get_databases |  |
