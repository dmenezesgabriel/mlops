## 06_iceberg_tables

| feature | status | detail | latency_ms |
|---|---|---|---|
| wr.athena.to_iceberg creates + loads an Iceberg table | PASS | nb06_ice_268d99ad: 3 row(s) read back | 2215.7 |
| Glue registration carries the Iceberg routing markers | PASS | table_type=ICEBERG; metadata_location=…/00001-7dbd2302-4125-4593-8869-0e765ff0be74.metadata.json; iceberg.field.current on 3 column(s) |  |
| wr.athena.to_iceberg appends to an existing table | PASS | 4 row(s) after the second write: ids=[1, 2, 3, 4] |  |
| wr.athena.delete_from_iceberg_table merge-deletes rows by key | PASS | deleted ids=[1, 3]; remaining=[2, 4] | 1097.18 |
| mixed Hive + Iceberg join routes per-reference on the Glue marker | PASS | nb06_hive_268d99ad (hive) ⨝ nb06_ice_268d99ad (iceberg) → 2 row(s) |  |
