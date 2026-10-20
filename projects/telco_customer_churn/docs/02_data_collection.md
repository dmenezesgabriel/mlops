# Data Collection

Data collection is the first physical step in our automated ML pipeline. In production, this step pulls CRM snapshot exports from the billing/subscription system of record — typically a nightly extract landed in an S3 data lake.

## Data Source

We use the **IBM Telco Customer Churn** sample dataset — the canonical open churn benchmark (7,043 customers × 21 attributes), originally published with IBM's churn-on-ICP4d accelerator and mirrored publicly. It models exactly the export a billing system would produce: one row per active customer, all attributes as-of the snapshot date.

Fields include:

- `customerID`: stable customer entity identifier — our Feast join key.
- `tenure`: months the customer has stayed on service.
- `Contract`: `Month-to-month`, `One year`, or `Two year` — the dominant churn driver in this dataset.
- `MonthlyCharges` / `TotalCharges`: billing amounts (`TotalCharges` arrives with blank strings for zero-tenure customers — handled in preprocessing).
- `InternetService`, `OnlineSecurity`, `OnlineBackup`, `DeviceProtection`, `TechSupport`, `StreamingTV`, `StreamingMovies`: subscribed product lines (`Yes`/`No`/`No internet service`).
- `PaymentMethod`, `PaperlessBilling`, `SeniorCitizen`, `Partner`, `Dependents`, `gender`, `PhoneService`, `MultipleLines`: demographic and billing-profile attributes.
- `Churn`: the label — `Yes`/`No`.

## Collection Contract

`python -m telco_customer_churn.prepare_data` performs the collection deterministically: if `data/raw/WA_Fn-UseC_-Telco-Customer-Churn.csv` is absent it downloads the pinned public URL, then writes the cleaned snapshot to `data/interim/customers_clean.parquet`. In production this would be a `collect` pipeline stage landing raw extracts in the lake; here the vendored fetch keeps the tutorial reproducible while `data/raw/` stays untracked (repo convention: only `.gitkeep` placeholders are committed under `data/`).

## Snapshot Semantics

The export is a **cross-sectional CRM snapshot** — one reference date (`2023-02-01`) for every customer. This matters downstream: Feast point-in-time joins need an `event_timestamp`, and the snapshot date becomes that timestamp, applied tz-aware UTC so the offline store's temporal filters compare like with like.
