## 03_data_engineering

| feature | status | detail | latency_ms |
|---|---|---|---|
| wr.s3.to_parquet(dataset=True) registers tables + partitions | PASS | nb03_orders_eec9a7ba + nb03_sales_eec9a7ba registered; sales partitions=[['EU'], ['US']] |  |
| wr.athena.create_ctas_table (named CTAS → Glue table + parquet) | PASS | 546eb4ed-e55d-45b1-942b-73e051e697a3 read back (2, 3); 1 object(s) at external_location; manifest=546eb4ed-e55d-45b1-942b-73e051e697a3-manifest.csv | 2307.38 |
| SSE_KMS EncryptionConfiguration on CTAS | PASS | EncryptionConfiguration={'EncryptionOption': 'SSE_KMS', 'KmsKey': 'arn:aws:kms:us-east-1:123456789012:key/00000000-0000-0000-0000-000000000000'} |  |
| wr.s3.to_parquet SSE-KMS write headers | PASS | objects=['kms/orders.parquet'] |  |
| generate_create_query emits CREATE EXTERNAL TABLE DDL | PASS | 562 chars; external=True partitioned=True |  |
| CREATE EXTERNAL TABLE via StartQueryExecution (Athena DDL) | PASS | 7b87f565-05f7-496a-be38-f8150a560931 SUCCEEDED; nb03_ext_eec9a7ba registered EXTERNAL_TABLE |  |
| ALTER TABLE … ADD PARTITION (Athena DDL) | PASS | 7f5db26a-0968-47fc-8438-de1a12e2a397 SUCCEEDED; Glue partitions=[['EU']]; read back (2, 2) |  |
| repair_table (MSCK REPAIR TABLE) discovers new partitions | PASS | final state SUCCEEDED |  |
| SHOW PARTITIONS <table> (Athena spelling) | PASS | 044042d9-43c9-4db5-92c9-c03a81b38771 → partitions ['EU', 'XX'] |  |
| "<table>$partitions" virtual table lists Glue partitions | PASS | Glue partitions=['EU', 'XX'] |  |
| wr.catalog.add_parquet_partitions registers a staged partition | PASS | 3 partitions after add: [['EU'], ['US'], ['AP']] |  |
| wr.catalog.delete_partitions unregisters a partition | PASS | 2 partitions after delete: [['EU'], ['US']] |  |
| wr.s3.store_parquet_metadata registers inferred schema + partitions | PASS | nb03_meta_eec9a7ba columns=['amount', 'quantity'] partition_types={'region': 'string'} values=[['EU'], ['US']] |  |
| read_sql_query unload_approach=True (UNLOAD → parquet read) | PASS | shape=(2, 3) |  |
| wr.athena.unload() writes a result set to S3 via UNLOAD | PASS | 3 object(s) incl. manifest under s3://nb03-bc2551affc2b/export/ |  |
| wr.s3.delete_objects removes a staged prefix | PASS | s3://nb03-bc2551affc2b/meta/sales/ emptied |  |
| wr.catalog.delete_all_partitions empties the registry | PASS | nb03_meta_eec9a7ba has 0 partitions |  |
| wr.catalog.delete_table_if_exists drops the table | PASS | nb03_meta_eec9a7ba absent from the catalog |  |
| wr.catalog.delete_database removes an empty database | PASS | nb03_scratch_eec9a7ba absent from get_databases |  |
