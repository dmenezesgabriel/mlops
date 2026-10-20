# Data preprocessing: a table that also wants to be a stream

Two output shapes come from one cleaned frame:

1. **Feast tables** — feature/label parquets with `market_tick_id` keys and
   true half-hour `event_timestamp`s, so training joins stay point-in-time.
2. **`stream_events.jsonl`** — the same ticks as newline-delimited JSON,
   the replay file `kafka_producer.py` pushes into the `market-ticks` topic.

Keeping both from one source guarantees the stream replays exactly what the
model trained on — no synthetic-event drift in the demo.

## Steps in `prepare_data.py`

1. Fetch ELEC2 via OpenML.
2. Coerce the seven market columns to numeric (raw file mixes dtypes).
3. Mint `market_tick_id` keys; rebase ticks to 30-minute timestamps.
4. Split features from labels; write both parquets + the schema contract.
5. Serialize the same feature rows as `stream_events.jsonl`.

## The contract

`feature_contract.py` pins the 7-column order the model consumes: channel
CSV header, Feast view schema, and the float vector the Flink job builds
from the tick payload all read the same constant. One order, three
consumers — the streaming path can't drift from the training path.
