"""Replay `stream_events.jsonl` into the `market-ticks` Kafka topic.

Simulates the upstream market feed at a steady cadence so the streaming
pipeline has live input without external dependencies.

Run:  python kafka_producer.py --events ../data/processed/stream_events.jsonl
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from kafka import KafkaProducer


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--topic", default="market-ticks")
    parser.add_argument("--bootstrap", default="kafka:9092")
    parser.add_argument(
        "--rate", type=float, default=50.0, help="events/second"
    )
    parser.add_argument("--limit", type=int, default=2000)
    args = parser.parse_args()
    producer = KafkaProducer(
        bootstrap_servers=args.bootstrap,
        value_serializer=lambda v: json.dumps(v).encode(),
    )
    sent = 0
    for line in args.events.read_text().splitlines()[: args.limit]:
        producer.send(args.topic, json.loads(line))
        sent += 1
        if sent % 100 == 0:
            producer.flush()
            print(f"sent {sent} ticks")
        time.sleep(1.0 / args.rate)
    producer.flush()
    print(f"done: {sent} ticks -> {args.topic}")


if __name__ == "__main__":
    main()
