import json
import logging
import sys


class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = {
            "time": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in (
            "diagram_id",
            "correlation_id",
            "output_path",
            "adapter",
            "duration_ms",
            "status",
        ):
            val = getattr(record, key, None)
            if val is not None:
                base[key] = val
        return json.dumps(base, default=str)


def setup_structured_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())
    root = logging.getLogger("diagrams_generation")
    root.addHandler(handler)
    root.setLevel(level)
