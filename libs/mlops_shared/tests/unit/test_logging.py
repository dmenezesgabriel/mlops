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
