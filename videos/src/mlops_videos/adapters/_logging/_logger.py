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
        for key in ("concept", "beat", "duration", "beats", "scene"):
            val = getattr(record, key, None)
            if val is not None:
                base[key] = val
        return json.dumps(base, default=str)


def setup_video_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())
    root = logging.getLogger("mlops_videos")
    root.addHandler(handler)
    root.setLevel(level)
