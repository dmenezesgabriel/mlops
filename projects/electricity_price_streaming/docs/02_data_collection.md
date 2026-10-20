# Data collection: the ELEC2 electricity stream

The dataset is **ELEC2** (Harries 1999) — 45,312 half-hourly ticks from the
New South Wales electricity market, distributed by OpenML as `electricity`.
It is *the* canonical stream-mining benchmark: concept drift is real, the
features are few and interpretable, and the binary label is whether NSW
price moves UP or DOWN next period.

## Fields

| Column | Meaning |
|---|---|
| `day` | Day of week (1–7) |
| `period` | Half-hour slot (0–1) |
| `nswprice` / `nswdemand` | NSW price and demand |
| `vicprice` / `vicdemand` | Victoria price and demand |
| `transfer` | Interconnector flow NSW↔VIC |
| `class` | **Label** — UP / DOWN |

## How it arrives here

`prepare_data.py` fetches the frame once and writes three artifacts:

- `market_features.parquet` — tick features (the Feast offline source).
- `direction_labels.parquet` — up/down labels, offline only.
- `stream_events.jsonl` — **the replay source**: one JSON tick per line,
  what the Kafka producer feeds into `market-ticks` during the demo.

The split mirrors production: the store holds tick state, the broker
carries the flow, and labels stay in their own table for training joins.

## Provenance notes

- Ticks are rebased onto real 1996 half-hour timestamps so Feast
  point-in-time semantics stay honest.
- ELEC2's documented drift (market rules changed mid-1997) is exactly the
  thing the monitoring stage watches for.
