import json
import logging
from datetime import UTC, datetime


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, sort_keys=True)


class MlopsLoggingConfigurator:
    """Configure project pipeline logging as line-delimited JSON.

    Example:
        MlopsLoggingConfigurator().configure()
    """

    def configure(self, level: int = logging.INFO) -> None:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonLogFormatter())
        logging.basicConfig(level=level, handlers=[handler], force=True)
