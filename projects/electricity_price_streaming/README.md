# electricity-price-streaming

Direction-of-next-move classification on the NSW electricity market, scored
**inside the event flow** — the same staged lifecycle as NYC taxi demand,
deployed the way stream scoring ships:

`Kafka → Flink → SageMaker endpoint → predictions topic`, with **Feast**
for the offline training join — the live scoring path reads each tick's own
market-state fields, because Feast's Kafka/stream sources are alpha and
Feast does not ingest from a topic. All Docker Compose, no AWS.

## Stack

- `docker-compose.yml` — `electricity-price-streaming-moto` (S3/DynamoDB),
  KRaft `kafka`, and a Flink `jobmanager`/`taskmanager` pair, all on
  `mlops_net`.
- `feature_repo/` — Feast repo: `market_profile` (online) +
  `direction_labels` (offline), used for the training join.
- `flink_job/` — `enrich_and_score.py` (tick features → endpoint → output
  topic) and `kafka_producer.py` (replays `stream_events.jsonl`).
- `src/electricity_price_streaming/` — `prepare_data.py` (ELEC2 → tables +
  replay stream), `feature_contract.py`, `train.py` (CatBoost).
- Images `electricity-price-streaming:train` / `:inference` —
  `make build-images`.

## Lifecycle notebooks

`index` → `eda` (drift is the story) → `feature_engineering` (compose +
Feast materialize) → `training` → `tuning` → `evaluation` (AUC gate) →
`deploy` (endpoint + topics + `flink run` + producer + consumer) →
`monitoring` (consumer lag + teardown). Narrative docs under `docs/`.

The async property is *decoupling*: topics buffer producers from consumers;
Flink invokes the synchronous endpoint per event.
