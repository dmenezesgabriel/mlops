from __future__ import annotations

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
        if record.exc_info:
            base["exception"] = self.formatException(record.exc_info)
        for key in (
            "concept_id",
            "scene_id",
            "render_id",
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
    root = logging.getLogger("videos")
    # cli.main() calls this every run — an unguarded addHandler piles a
    # duplicate handler per call for process life (each record emitted N×).
    # setLevel stays unconditional so repeat calls still apply a new level.
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredFormatter())
        root.addHandler(handler)
    root.setLevel(level)
