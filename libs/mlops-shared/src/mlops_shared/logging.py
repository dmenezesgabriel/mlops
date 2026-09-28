import json
import logging
from datetime import UTC, datetime
from typing import TypeAlias, TypeGuard

JsonValue: TypeAlias = str | int | float | bool | None

_LOG_RECORD_KEYS = set(logging.makeLogRecord({}).__dict__)
# Payload fields owned by JsonLogFormatter.format: `extra=` is allowed to set
# these as record attrs, so without this filter they would spoof the emitted
# level/timestamp/logger/exception.
_RESERVED_PAYLOAD_KEYS = frozenset(
    {"timestamp", "level", "logger", "message", "exception"}
)


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

    def _extra_context(
        self, record: logging.LogRecord
    ) -> dict[str, JsonValue]:
        return {
            key: self._json_safe(value)
            for key, value in record.__dict__.items()
            if key not in _LOG_RECORD_KEYS
            and key not in _RESERVED_PAYLOAD_KEYS
        }

    def _json_safe(self, value: object) -> JsonValue:
        if self._is_json_scalar(value):
            return value
        return str(value)

    def _is_json_scalar(self, value: object) -> TypeGuard[JsonValue]:
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
