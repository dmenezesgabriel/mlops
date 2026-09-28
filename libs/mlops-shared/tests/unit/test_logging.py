import io
import json
import logging
import sys

from mlops_shared.logging import JsonLogFormatter, MlopsLoggingConfigurator


def test_json_log_formatter_includes_structured_context() -> None:
    # Arrange
    record = logging.LogRecord(
        name="pipeline",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="pipeline_started",
        args=(),
        exc_info=None,
    )

    # Act
    payload = json.loads(JsonLogFormatter().format(record))

    # Assert
    assert payload["level"] == "INFO"
    assert payload["logger"] == "pipeline"
    assert payload["message"] == "pipeline_started"


def test_json_log_formatter_includes_extra_context() -> None:
    # Arrange
    record = logging.LogRecord(
        name="pipeline",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="pipeline_started",
        args=(),
        exc_info=None,
    )
    record.correlation_id = "run-1"

    # Act
    payload = json.loads(JsonLogFormatter().format(record))

    # Assert
    assert payload["correlation_id"] == "run-1"


def test_json_log_formatter_extra_cannot_override_reserved_fields() -> None:
    # Arrange
    record = logging.LogRecord(
        name="pipeline",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="pipeline_failed",
        args=(),
        exc_info=None,
    )
    record.level = "SPOOFED"
    record.timestamp = "1970-01-01T00:00:00+00:00"
    record.logger = "forged-logger"
    record.exception = "forged traceback"

    # Act
    payload = json.loads(JsonLogFormatter().format(record))

    # Assert
    assert payload["level"] == "ERROR"
    assert payload["logger"] == "pipeline"
    assert payload["timestamp"] != "1970-01-01T00:00:00+00:00"
    assert "exception" not in payload


def test_json_log_formatter_stringifies_non_scalar_extra() -> None:
    # Arrange
    record = logging.LogRecord(
        name="pipeline",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="pipeline_started",
        args=(),
        exc_info=None,
    )
    record.context = {"renderer": "markdown"}

    # Act
    payload = json.loads(JsonLogFormatter().format(record))

    # Assert
    assert payload["context"] == "{'renderer': 'markdown'}"


def test_json_log_formatter_includes_exception_details() -> None:
    # Arrange
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        exc_info = sys.exc_info()
    record = logging.LogRecord(
        name="pipeline",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="pipeline_failed",
        args=(),
        exc_info=exc_info,
    )

    # Act
    payload = json.loads(JsonLogFormatter().format(record))

    # Assert
    assert "RuntimeError: boom" in payload["exception"]


def test_mlops_logging_configurator_emits_json_to_root_logger() -> None:
    # Arrange — configure() calls basicConfig(force=True), which would close
    # pytest's capture handlers; detach them first, restore after.
    previous_handlers = logging.root.handlers
    previous_level = logging.root.level
    logging.root.handlers = []
    try:
        # Act
        MlopsLoggingConfigurator().configure(level=logging.WARNING)
        handler = logging.root.handlers[0]
        stream = io.StringIO()
        handler.setStream(stream)
        logging.getLogger("pipeline").warning("configured")

        # Assert
        assert isinstance(handler, logging.StreamHandler)
        assert isinstance(handler.formatter, JsonLogFormatter)
        assert logging.root.level == logging.WARNING
        payload = json.loads(stream.getvalue())
        assert payload["level"] == "WARNING"
        assert payload["logger"] == "pipeline"
        assert payload["message"] == "configured"
    finally:
        for added_handler in logging.root.handlers:
            added_handler.close()
        logging.root.handlers = previous_handlers
        logging.root.level = previous_level
