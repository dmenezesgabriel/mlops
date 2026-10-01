import json
import logging
from datetime import UTC, datetime
from typing import TypeAlias, TypeGuard, cast

JsonValue: TypeAlias = str | int | float | bool | None


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        context = self._context(record)
        if context:
            payload["context"] = context

        return json.dumps(payload, sort_keys=True)

    def _context(self, record: logging.LogRecord) -> dict[str, JsonValue]:
        context = getattr(record, "context", {})
        if isinstance(context, dict):
            context_map = cast(dict[object, object], context)
            return {
                str(key): self._json_safe(value)
                for key, value in context_map.items()
            }

        return {"value": str(context)}

    def _json_safe(self, value: object) -> JsonValue:
        if self._is_json_scalar(value):
            return value
        return str(value)

    def _is_json_scalar(self, value: object) -> TypeGuard[JsonValue]:
        return isinstance(value, str | int | float | bool) or value is None


class StructuredLoggingConfigurator:
    """Configure SSG logs without depending on shared MLOps libraries.

    Example:
        StructuredLoggingConfigurator().configure()
    """

    def configure(self, level: int = logging.INFO) -> None:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonLogFormatter())
        logging.basicConfig(level=level, handlers=[handler], force=True)
