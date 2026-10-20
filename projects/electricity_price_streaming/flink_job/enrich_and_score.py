"""PyFlink job: Kafka ticks -> endpoint -> out.

Reads raw market ticks from the `market-ticks` topic, builds the model's
feature vector from the tick's own market-state fields, invokes the SageMaker
endpoint, and writes scored predictions to the `price-predictions` topic.

The streaming path deliberately does not call Feast: Feast's stream sources
(Kafka/Kinesis) are alpha and Feast does not ingest from a topic, and each
tick already carries the market state the model was trained on. Feast stays
on the offline training join; it is not part of the live scoring path.

Run inside the flink taskmanager image (pyflink installed):
  flink run -py /opt/flink_job/enrich_and_score.py
"""

from __future__ import annotations

import json
import os
import urllib.request

from pyflink.datastream import StreamExecutionEnvironment

SOURCE_TOPIC = os.environ.get("KAFKA_SOURCE_TOPIC", "market-ticks")
SINK_TOPIC = os.environ.get("KAFKA_SINK_TOPIC", "price-predictions")
BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
ENDPOINT_URL = os.environ.get("SAGEMAKER_ENDPOINT_URL", "")
FEATURES = [
    "day",
    "period",
    "nswprice",
    "nswdemand",
    "vicprice",
    "vicdemand",
    "transfer",
]


class ScoreTick:
    """Build one tick's feature vector and invoke the endpoint."""

    def score(self, raw: str) -> str:
        event = json.loads(raw)
        tick_id = event["market_tick_id"]
        vector = [[float(event[feature]) for feature in FEATURES]]
        request = urllib.request.Request(
            ENDPOINT_URL,
            data=json.dumps(vector).encode(),
            headers={"Content-Type": "application/json"},
        )
        # ENDPOINT_URL is operator config (SAGEMAKER_ENDPOINT_URL), not event
        # data: what comes off the topic is the vector, never the URL.
        prediction = json.loads(
            urllib.request.urlopen(  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
                request, timeout=30
            ).read()
        )
        return json.dumps(
            {"market_tick_id": tick_id, "prediction": prediction}
        )


def main() -> None:
    env = StreamExecutionEnvironment.get_execution_environment()
    env.add_jars("file:///opt/flink/lib/flink-sql-connector-kafka-*.jar")
    # DataStream path: raw strings -> map through the scorer -> kafka sink.
    from pyflink.common.serialization import SimpleStringSchema
    from pyflink.datastream.connectors.kafka import (
        KafkaRecordSerializationSchema,
        KafkaSink,
        KafkaSource,
    )

    kafka_source = (
        KafkaSource.builder()
        .set_bootstrap_servers(BOOTSTRAP)
        .set_topics(SOURCE_TOPIC)
        .set_group_id("flink-scorer")
        .set_starting_offsets(
            __import__(
                "pyflink.datastream.connectors.kafka",
                fromlist=["KafkaOffsetsInitializer"],
            ).KafkaOffsetsInitializer.earliest()
        )
        .set_value_only_deserializer(SimpleStringSchema())
        .build()
    )
    kafka_sink = (
        KafkaSink.builder()
        .set_bootstrap_servers(BOOTSTRAP)
        .set_record_serializer(
            KafkaRecordSerializationSchema.builder()
            .set_topic(SINK_TOPIC)
            .set_value_serialization_schema(SimpleStringSchema())
            .build()
        )
        .build()
    )
    scorer = ScoreTick()
    stream = env.from_source(
        kafka_source,
        __import__(
            "pyflink.common", fromlist=["WatermarkStrategy"]
        ).WatermarkStrategy.no_watermarks(),
        "ticks",
    )
    stream.map(scorer.score).sink_to(kafka_sink)
    env.execute("electricity-price-scoring")


if __name__ == "__main__":
    main()
