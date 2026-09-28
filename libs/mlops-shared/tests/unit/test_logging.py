import json
import logging

from mlops_shared.logging import JsonLogFormatter


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
