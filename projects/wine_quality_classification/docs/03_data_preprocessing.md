# Data preprocessing: entity keys, split tables, and why a scaler rides in
the model

The chemistry arrives clean — preprocessing is structural. `prepare_data.py`
renames, mints `wine_id` keys, attaches the snapshot timestamp, splits
features from labels, and writes `feature_schema.json` as the contract.

One real modelling decision lives in `train.py` rather than here: the
thirteen measures span wildly different scales (proline ~1500 vs hue ~1).
The `StandardScaler` goes **inside the sklearn pipeline** that becomes
`model.joblib`, so serving never has to know scaling exists — the artifact
is self-contained.

## The contract

`feature_contract.py` pins the 13-column order consumed by the model: the
same constant drives the channel CSV header, the Feast view schema, and the
pipeline's training step. One order, no train/serve drift.
