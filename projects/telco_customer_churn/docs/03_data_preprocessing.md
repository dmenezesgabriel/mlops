# Data Preprocessing & Feature Engineering

The raw CRM export is human-readable but not model-readable: categorical strings need encoding, money fields need numeric coercion, and the service catalog needs consolidation into counts the model can weigh.

---

## 1. The Preprocessing Transformation Pipeline

`prepare_data.py` applies a deterministic sequence:

1. **Type normalization** — `TotalCharges` contains blank strings (`" "`) for brand-new customers with no billing history. We coerce to numeric and fill with `0.0` (a zero-tenure customer has legitimately paid nothing — filling with `MonthlyCharges` would fabricate revenue).
2. **Entity & label projection** — `customerID` → `customer_id` (the Feast entity key); `Churn` (`Yes`/`No`) → `churn` (`1`/`0`).
3. **Categorical encoding** — the two contract values most predictive of retention (`Month-to-month`, `One year`) become indicator columns, with `Two year` as the reference level; `DSL`/`Fiber optic` become indicators with `No` service as reference; `PaymentMethod` collapses to `electronic_check` (the method strongly associated with churn); `Partner`, `Dependents`, `SeniorCitizen`, `PaperlessBilling` become 0/1 flags.
4. **Service consolidation** — the six add-on columns (`OnlineSecurity`, `OnlineBackup`, `DeviceProtection`, `TechSupport`, `StreamingTV`, `StreamingMovies`) are summed into `num_add_ons`, with `streaming_tv`/`streaming_movies` also kept individually (media services behave differently from protection services in churn studies).
5. **Snapshot timestamping** — `event_timestamp = 2023-02-01` tz-aware UTC, matching the export's snapshot semantics so Feast temporal filters compare like with like.

---

## 2. Output Contracts

| Artifact | Role downstream |
|---|---|
| `data/interim/customers_clean.parquet` | Typed CRM snapshot — input to EDA |
| `data/processed/customer_features.parquet` | **Feast offline source** — entity + `event_timestamp` + 15 feature columns in contract order |
| `data/processed/churn_labels.parquet` | Label `entity_df` — `customer_id` + `event_timestamp` + `churn`, joined to features at training time via `get_historical_features` |
| `data/processed/scoring_entities.parquet` | Scoring `entity_df` — the full population, no labels, joined at batch time |
| `data/processed/feature_schema.json` | Ordered feature list + entity/label names — consumed by notebooks to order transform inputs |

The separation is deliberate: **features live without the label** (the offline store serves both labeled training joins and unlabeled scoring joins from the same source), and the label joins only through Feast's point-in-time correct retrieval — the same mechanism that prevents training-serving skew.

---

## 3. Training-Serving Skew Prevention

Because both the training dataset and the batch-scoring input are produced by `get_historical_features` against the *same* feature view over the *same* parquet, the columns arriving at the model are bitwise identical in name, order, and encoding logic — there is exactly one feature pipeline (`prepare_data.py` → `feature_views.py`) and no parallel inference-time reimplementation to drift out of sync.
