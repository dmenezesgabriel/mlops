## 05_wrangler_write_catalog_and_gaps

| feature | status | detail | latency_ms |
|---|---|---|---|
| wr.s3.to_parquet(dataset=True) registers tables + partitions | PASS | nb05_orders_eefb90e6 + nb05_sales_eefb90e6 registered; sales partitions=[['EU'], ['US']] |  |
| wr.athena.create_ctas_table (named CTAS → Glue table + parquet) | PASS | 6399ce5a-c543-45f4-b0d8-808d5ec7f7ee read back (2, 3); 1 object(s) at external_location; manifest=6399ce5a-c543-45f4-b0d8-808d5ec7f7ee-manifest.csv | 2227 |
| generate_create_query emits CREATE EXTERNAL TABLE DDL | PASS | 562 chars; external=True partitioned=True |  |
| wr.catalog.add_parquet_partitions registers a staged partition | PASS | 3 partitions after add: [['EU'], ['US'], ['AP']] |  |
| wr.catalog.delete_partitions unregisters a partition | PASS | 2 partitions after delete: [['EU'], ['US']] |  |
| wr.s3.store_parquet_metadata registers inferred schema + partitions | PASS | nb05_meta_eefb90e6 columns=['amount', 'quantity'] partition_types={'region': 'string'} values=[['EU'], ['US']] |  |
| wr.s3.delete_objects removes a staged prefix | PASS | s3://nb05-fd14d2eae2ac/meta/sales/ emptied |  |
| wr.catalog.delete_all_partitions empties the registry | PASS | nb05_meta_eefb90e6 has 0 partitions |  |
| wr.catalog.delete_table_if_exists drops the table | PASS | nb05_meta_eefb90e6 absent from the catalog |  |
| wr.catalog.delete_database removes an empty database | PASS | nb05_scratch_eefb90e6 absent from get_databases |  |
| CREATE EXTERNAL TABLE via StartQueryExecution (Athena DDL) | PASS | SUCCEEDED: ed073db5-a1a2-43ae-96be-8c70277196bc |  |
| ALTER TABLE … ADD PARTITION (Athena DDL) | PASS | SUCCEEDED: 8dd0fc78-168c-4ed0-ac11-e085303c4c6f |  |
| wr.athena.to_iceberg (Iceberg table write) | PASS | created |  |
| wr.athena.delete_from_iceberg_table (row delete) | PASS | deleted |  |
| SSE_KMS EncryptionConfiguration on CTAS | PASS | EncryptionConfiguration={'EncryptionOption': 'SSE_KMS', 'KmsKey': 'arn:aws:kms:us-east-1:123456789012:key/00000000-0000-0000-0000-000000000000'} |  |
| wr.s3.to_parquet SSE-KMS write headers | PASS | objects=['kms/orders.parquet'] |  |
| out-of-scope create_capacity_reservation → shaped InvalidRequestException | PASS | InvalidRequestException (400): Operation CreateCapacityReservation is not yet implemented by the emulator |  |
| out-of-scope list_capacity_reservations → shaped InvalidRequestException | PASS | InvalidRequestException (400): Operation ListCapacityReservations is not yet implemented by the emulator |  |
| out-of-scope create_notebook → shaped InvalidRequestException | PASS | InvalidRequestException (400): Operation CreateNotebook is not yet implemented by the emulator |  |
| out-of-scope list_sessions → shaped InvalidRequestException | PASS | InvalidRequestException (400): Operation ListSessions is not yet implemented by the emulator |  |
