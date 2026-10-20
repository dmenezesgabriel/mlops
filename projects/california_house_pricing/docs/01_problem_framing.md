# Problem framing: instant price estimates for California block groups

A lending-adjacent product team wants an estimated home value the moment a
user enters an address — not a nightly spreadsheet. The natural unit is the
census block group: the features that drive value (median income, housing
age, occupancy, location) are measured per block group, and the estimate
serves one HTTP round-trip per request.

That requirement fixes the deployment shape before any modelling starts:

- **Latency**: a human is waiting — the estimate must come back in tens of
  milliseconds. A batch job that runs tonight is the wrong tool.
- **Request pattern**: unpredictable, interactive, one record at a time.
- **Feature freshness**: block-group attributes change slowly (census
  cadence), so they can be precomputed and pushed to an online store rather
  than recomputed per request.

So this project is a **synchronous SageMaker endpoint backed by a Feast
online store**: Feast materializes block-group features into DynamoDB, the
endpoint receives a feature vector, scores it, and returns the estimate in
the same request.

## The decision being made

| Question | Answer |
|---|---|
| Who consumes the output? | Interactive valuation UI / API callers |
| What unit? | One census block group (`block_group_id`) |
| What is predicted? | Median house value (regression, $100k units) |
| How fresh? | Features at census cadence; score at request time |
| Wrong is worse when? | Overestimating high-value areas — measured by MAE |

## Why not the other shapes

- **Batch transform** (see `telco_customer_churn`): fine for scoring every
  known entity on a schedule — wrong when requests arrive one at a time.
- **Streaming** (see `electricity_price_streaming`): useful when events
  arrive continuously and must be scored as they flow — block groups don't
  stream, they get looked up.

## Success criteria

- R² ≥ 0.75 and MAE ≲ 0.4 (in $100k units) on the holdout.
- p50 invoke latency well under 100 ms once the endpoint is warm.
- `feast materialize` → `get_online_features` returns the same values the
  offline table holds (store consistency check in the deploy notebook).
