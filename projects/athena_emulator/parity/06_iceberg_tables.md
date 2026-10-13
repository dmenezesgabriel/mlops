## 06_iceberg_tables

| feature | status | detail | latency_ms |
|---|---|---|---|
| wr.athena.to_iceberg creates + loads an Iceberg table | PASS | nb06_ice_875adf2c: 3 row(s) read back | 2220.21 |
| Glue registration carries the Iceberg routing markers | PASS | table_type=ICEBERG; metadata_location=…/00001-6da8dfb3-8a1c-4a2f-9916-4ebff002d066.metadata.json; iceberg.field.current on 3 column(s) |  |
| wr.athena.to_iceberg appends to an existing table | PASS | 4 row(s) after the second write: ids=[1, 2, 3, 4] |  |
| wr.athena.delete_from_iceberg_table merge-deletes rows by key | PASS | deleted ids=[1, 3]; remaining=[2, 4] | 1092.18 |
| mixed Hive + Iceberg join routes per-reference on the Glue marker | PASS | nb06_hive_875adf2c (hive) ⨝ nb06_ice_875adf2c (iceberg) → 2 row(s) |  |
