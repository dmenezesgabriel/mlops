# Problem framing: cultivar classification as a managed pipeline

A winery lab measures thirteen physicochemical properties per sample and
wants the cultivar predicted — but the real ask isn't a model, it's a
**repeatable process**: data in, model out, every step versioned and
re-runnable without a human clicking through notebooks.

That fixes the deployment shape: a **SageMaker Pipeline** — the lifecycle
itself is the artifact. This project pairs the pipeline with a **Feast
offline store** that builds the training set point-in-time correctly, so the
pipeline's first step is a store retrieval, not a hand-rolled CSV.

## The decision being made

| Question | Answer |
|---|---|
| Who consumes the output? | Lab reporting + downstream blending decisions |
| What unit? | One wine sample (`wine_id`) |
| What is predicted? | Cultivar class (3-way classification) |
| Why a pipeline? | Retraining is routine; steps must be auditable |
| Wrong is worse when? | Mislabeling premium cultivars — accuracy gate |

## Why not the other shapes

- **Sync endpoint** (`california_house_pricing`): the lab scores batches of
  samples after assays, not one interactive request at a time.
- **Streaming** (`electricity_price_streaming`): assays don't stream.
- **Batch transform** (`telco_customer_churn`): close, but the point of
  this example is orchestration — the pipeline *contains* the scoring step.

## Success criteria

- Pipeline runs `LocalPipelineSession` end to end: retrieval → train →
  evaluate → condition → register.
- Holdout accuracy ≥ 0.9 (the dataset is famously separable).
