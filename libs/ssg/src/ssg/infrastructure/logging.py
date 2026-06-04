import json
import logging
from datetime import UTC, datetime


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

    def _context(self, record: logging.LogRecord) -> dict[str, object]:
        context = getattr(record, "context", {})
        if isinstance(context, dict):
            return {str(key): value for key, value in context.items()}

        return {"value": str(context)}


class StructuredLoggingConfigurator:
    """Configure SSG logs without depending on shared MLOps libraries.

    Example:
        StructuredLoggingConfigurator().configure()
    """

    def configure(self, level: int = logging.INFO) -> None:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonLogFormatter())
        logging.basicConfig(level=level, handlers=[handler], force=True)
