# Data collection: the 1990 California census

The dataset is the classic California housing data — 20,640 census block
groups from the 1990 census, distributed by `sklearn.datasets
.fetch_california_housing` (originally Pace & Barry 1997). It is open,
small and reproducible, which is why it is a standard regression benchmark.

## Fields

| Column | Meaning |
|---|---|
| `median_income` | Median household income, in tens of thousands |
| `house_age` | Median age of houses in the block group |
| `avg_rooms` / `avg_bedrooms` | Average rooms / bedrooms per household |
| `population` | Block-group population |
| `avg_occupancy` | Average household size |
| `latitude` / `longitude` | Geographic position |
| `median_house_value` | **Label** — median home value, in $100k units |

## How it arrives here

`prepare_data.py` fetches the frame once, renames the raw sklearn columns
to business names, assigns each row a stable `block_group_id` entity key
plus a shared `event_timestamp`, and splits it into two parquet tables:

- `block_group_features.parquet` — the attributes Feast materializes online.
- `house_values.parquet` — labels, offline only (leakage guard).

Splitting features from labels mirrors production: a feature store serves
attributes to whoever needs them, while labels live in a separate table so
nothing accidentally trains on tomorrow's answer.

## Provenance notes

- Values are top-coded ($500k median cap) — a known dataset limitation
  worth remembering when estimates pile up at the boundary.
- The shared `event_timestamp` stands in for a census snapshot date; a real
  feed would carry per-record `as_of` dates.
