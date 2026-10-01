import json
import logging

from ssg.infrastructure.logging import JsonLogFormatter


def _record() -> logging.LogRecord:
    return logging.LogRecord(
        name="ssg",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="page_built",
        args=(),
        exc_info=None,
    )


def test_json_log_formatter_preserves_scalar_context_values() -> None:
    # Arrange
    record = _record()
    record.context = {"renderer": "markdown", "attempt": 2}

    # Act
    payload = json.loads(JsonLogFormatter().format(record))

    # Assert
    assert payload["context"] == {"renderer": "markdown", "attempt": 2}


def test_json_log_formatter_stringifies_non_scalar_context_value() -> None:
    # Arrange
    record = _record()
    record.context = {"renderer": object()}

    # Act
    payload = json.loads(JsonLogFormatter().format(record))

    # Assert
    value = payload["context"]["renderer"]
    assert isinstance(value, str)
    assert value.startswith("<object object at 0x")


def test_json_log_formatter_stringifies_nested_dict_context_value() -> None:
    # Arrange
    record = _record()
    record.context = {"stats": {"pages": 3}}

    # Act
    payload = json.loads(JsonLogFormatter().format(record))

    # Assert
    assert payload["context"]["stats"] == "{'pages': 3}"


def test_json_log_formatter_stringifies_non_dict_context() -> None:
    # Arrange
    record = _record()
    record.context = "plain"

    # Act
    payload = json.loads(JsonLogFormatter().format(record))

    # Assert
    assert payload["context"] == {"value": "plain"}
