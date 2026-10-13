## 06_iceberg_tables

| feature | status | detail | latency_ms |
|---|---|---|---|
| wr.athena.to_iceberg creates + loads an Iceberg table | PASS | nb06_ice_73df8954: 3 row(s) read back | 4462.03 |
| Glue registration carries the Iceberg routing markers | PASS | table_type=ICEBERG; metadata_location=…/00001-7bdb4a97-1a7e-4ad9-8523-44883b6ee697.metadata.json; iceberg.field.current on 3 column(s) |  |
| wr.athena.to_iceberg appends to an existing table | PASS | 4 row(s) after the second write: ids=[1, 2, 3, 4] |  |
| wr.athena.delete_from_iceberg_table merge-deletes rows by key | PASS | deleted ids=[1, 3]; remaining=[2, 4] | 2390.25 |
| mixed Hive + Iceberg join routes per-reference on the Glue marker | PASS | nb06_hive_73df8954 (hive) ⨝ nb06_ice_73df8954 (iceberg) → 2 row(s) |  |
