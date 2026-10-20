# Data preprocessing: entity keys and Feast tables

Preprocessing here is deliberately light — the census numbers arrive clean
and already aggregated to block-group level. The work that matters is
structural, not statistical:

## Steps in `prepare_data.py`

1. **Fetch** the sklearn frame (cached by sklearn after the first call).
2. **Rename** raw columns to business names so the parquet schema reads
   like the domain, not like the 1997 paper.
3. **Mint entity keys** — `bg-00000` … `bg-20639` — stable identifiers a
   caller can look up online.
4. **Attach `event_timestamp`** — a shared snapshot date so Feast treats
   every row as the current census state.
5. **Split** features from labels into separate parquet tables.
6. **Write `feature_schema.json`** — the machine-readable contract the
   notebooks and tests assert against.

## What is intentionally absent

- **No scaling** — LightGBM is a tree ensemble; monotonic transforms don't
  change its splits.
- **No imputation** — the census data has no missing values; a real feed
  would get a `na` policy at this stage.
- **No outlier clipping** — the $500k top-coding is a property of the data,
  documented in collection, not silently "fixed".

## The contract

`feature_contract.py` pins the positional column order the model consumes:
the same constant drives the CSV header written for the training channel,
the Feast view schema, and the float vector sent to the endpoint. One order,
three consumers — no drift between training and serving.
