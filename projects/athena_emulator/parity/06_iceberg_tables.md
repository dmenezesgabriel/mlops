## 06_iceberg_tables

| feature | status | detail | latency_ms |
|---|---|---|---|
| wr.athena.to_iceberg creates + loads an Iceberg table | PASS | nb06_ice_89c31dd2: 3 row(s) read back | 2408.83 |
| Glue registration carries the Iceberg routing markers | PASS | table_type=ICEBERG; metadata_location=…/00001-e0b5ebb4-bc40-4054-9806-fa545996da4a.metadata.json; iceberg.field.current on 3 column(s) |  |
| wr.athena.to_iceberg appends to an existing table | PASS | 4 row(s) after the second write: ids=[1, 2, 3, 4] |  |
| wr.athena.delete_from_iceberg_table merge-deletes rows by key | PASS | deleted ids=[1, 3]; remaining=[2, 4] | 1218.95 |
| mixed Hive + Iceberg join routes per-reference on the Glue marker | PASS | nb06_hive_89c31dd2 (hive) ⨝ nb06_ice_89c31dd2 (iceberg) → 2 row(s) |  |
