## 05_wrangler_write_catalog_and_gaps

| feature | status | detail | latency_ms |
|---|---|---|---|
| wr.s3.to_parquet(dataset=True) registers tables + partitions | PASS | nb05_orders_ecdee0a5 + nb05_sales_ecdee0a5 registered; sales partitions=[['EU'], ['US']] |  |
| wr.athena.create_ctas_table (named CTAS → Glue table + parquet) | PASS | f25584e1-3778-4e31-a25a-116fba40982c read back (2, 3); 1 object(s) at external_location; manifest=f25584e1-3778-4e31-a25a-116fba40982c-manifest.csv | 2514.48 |
| generate_create_query emits CREATE EXTERNAL TABLE DDL | PASS | 562 chars; external=True partitioned=True |  |
| wr.catalog.add_parquet_partitions registers a staged partition | PASS | 3 partitions after add: [['EU'], ['US'], ['AP']] |  |
| wr.catalog.delete_partitions unregisters a partition | PASS | 2 partitions after delete: [['EU'], ['US']] |  |
| wr.s3.store_parquet_metadata registers inferred schema + partitions | PASS | nb05_meta_ecdee0a5 columns=['amount', 'quantity'] partition_types={'region': 'string'} values=[['EU'], ['US']] |  |
| wr.s3.delete_objects removes a staged prefix | PASS | s3://nb05-c6a8f99f9cf5/meta/sales/ emptied |  |
| wr.catalog.delete_all_partitions empties the registry | PASS | nb05_meta_ecdee0a5 has 0 partitions |  |
| wr.catalog.delete_table_if_exists drops the table | PASS | nb05_meta_ecdee0a5 absent from the catalog |  |
| wr.catalog.delete_database removes an empty database | PASS | nb05_scratch_ecdee0a5 absent from get_databases |  |
| CREATE EXTERNAL TABLE via StartQueryExecution (Athena DDL) | PASS | SUCCEEDED: 3ee5f20f-36ec-4312-a229-753ff85f8e61 |  |
| ALTER TABLE … ADD PARTITION (Athena DDL) | PASS | SUCCEEDED: b51cd8d4-5576-4dc9-a8ae-f3ec7339e407 |  |
| wr.athena.to_iceberg (Iceberg table write) | PASS | created |  |
| wr.athena.delete_from_iceberg_table (row delete) | PASS | deleted |  |
| SSE_KMS EncryptionConfiguration on CTAS | PASS | EncryptionConfiguration={'EncryptionOption': 'SSE_KMS', 'KmsKey': 'arn:aws:kms:us-east-1:123456789012:key/00000000-0000-0000-0000-000000000000'} |  |
| wr.s3.to_parquet SSE-KMS write headers | PASS | objects=['kms/orders.parquet'] |  |
| out-of-scope create_capacity_reservation → shaped InvalidRequestException | PASS | InvalidRequestException (400): Operation CreateCapacityReservation is not yet implemented by the emulator |  |
| out-of-scope list_capacity_reservations → shaped InvalidRequestException | PASS | InvalidRequestException (400): Operation ListCapacityReservations is not yet implemented by the emulator |  |
| out-of-scope create_notebook → shaped InvalidRequestException | PASS | InvalidRequestException (400): Operation CreateNotebook is not yet implemented by the emulator |  |
| out-of-scope list_sessions → shaped InvalidRequestException | PASS | InvalidRequestException (400): Operation ListSessions is not yet implemented by the emulator |  |
