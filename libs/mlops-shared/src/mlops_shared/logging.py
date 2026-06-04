import json
import logging
from datetime import UTC, datetime
from typing import TypeAlias

JsonValue: TypeAlias = str | int | float | bool | None

_LOG_RECORD_KEYS = set(logging.makeLogRecord({}).__dict__)


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, JsonValue] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        payload.update(self._extra_context(record))

        return json.dumps(payload, sort_keys=True)

    def _extra_context(self, record: logging.LogRecord) -> dict[str, JsonValue]:
        return {
            key: value
            for key, value in record.__dict__.items()
            if key not in _LOG_RECORD_KEYS and key != "message" and self._is_json_scalar(value)
        }

    def _is_json_scalar(self, value: object) -> bool:
        return isinstance(value, str | int | float | bool) or value is None


class MlopsLoggingConfigurator:
    """Configure project pipeline logging as line-delimited JSON.

    Example:
        MlopsLoggingConfigurator().configure()
    """

    def configure(self, level: int = logging.INFO) -> None:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonLogFormatter())
        logging.basicConfig(level=level, handlers=[handler], force=True)
