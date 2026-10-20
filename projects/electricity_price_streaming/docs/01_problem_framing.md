# Problem framing: scoring a market feed as it flows

An energy trading desk watches NSW/VIC market ticks — half-hourly prices,
demand, interconnector flow — and wants each tick classified: will NSW price
move **UP or DOWN** next period? The input isn't a table someone uploads; it
is a **continuous event stream**. Scoring must happen *inside* the flow, not
in a nightly batch and not as a request someone remembers to send.

That fixes the deployment shape:

- **Events arrive continuously** → a message broker (Kafka) owns the ingest.
- **Stateless scoring at stream rate** → a stream processor (Flink) maps
  each event through the model path.
- **Slowly-changing context** (the tick's market profile) → carried on the
  tick itself; the live path does not call Feast (its Kafka/stream sources
  are alpha and it does not ingest from a topic).
- **The model** → a synchronous SageMaker endpoint; the "async" of this
  architecture is the *stream decoupling*, not the call — Flink invokes the
  endpoint per event and writes scored predictions to an output topic.

`Kafka → Flink (tick features) → SageMaker endpoint → predictions topic`

## The decision being made

| Question | Answer |
|---|---|
| Who consumes the output? | Downstream consumers of `price-predictions` |
| What unit? | One market tick (`market_tick_id`) |
| What is predicted? | Direction of next NSW price move (up/down) |
| Why streaming? | Producers and consumers are decoupled by topics |
| Wrong is worse when? | Missing sustained up-moves — AUC/accuracy gate |

## Why not the other shapes

- **Batch transform** (`telco_customer_churn`): a nightly job can't score
  events that arrive between runs.
- **Sync endpoint alone** (`california_house_pricing`): nothing pulls the
  trigger — ticks must be scored as they arrive, without a caller.
- **Pipeline** (`wine_quality_classification`): orchestrates retraining,
  not per-event scoring.

## Success criteria

- Holdout AUC ≥ 0.75.
- End-to-end: tick produced → feature vector built → endpoint scored →
  prediction appears on the output topic.
