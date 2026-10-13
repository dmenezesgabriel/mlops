## 06_iceberg_tables

| feature | status | detail | latency_ms |
|---|---|---|---|
| wr.athena.to_iceberg creates + loads an Iceberg table | PASS | nb06_ice_3ae59837: 3 row(s) read back | 3249.88 |
| Glue registration carries the Iceberg routing markers | PASS | table_type=ICEBERG; metadata_location=…/00001-3723505a-0c5f-4cec-8b86-94e6b4c1dc55.metadata.json; iceberg.field.current on 3 column(s) |  |
| wr.athena.to_iceberg appends to an existing table | PASS | 4 row(s) after the second write: ids=[1, 2, 3, 4] |  |
| wr.athena.delete_from_iceberg_table merge-deletes rows by key | PASS | deleted ids=[1, 3]; remaining=[2, 4] | 2187.8 |
| mixed Hive + Iceberg join routes per-reference on the Glue marker | PASS | nb06_hive_3ae59837 (hive) ⨝ nb06_ice_3ae59837 (iceberg) → 2 row(s) |  |
