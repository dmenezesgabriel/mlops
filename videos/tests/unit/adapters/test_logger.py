import json
import logging

from mlops_videos.adapters._logging._logger import StructuredFormatter


def test_structured_formatter_includes_basic_fields() -> None:
    record = logging.LogRecord(
        name="mlops_videos.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="scene_started",
        args=(),
        exc_info=None,
    )
    payload = json.loads(StructuredFormatter().format(record))
    assert payload["level"] == "INFO"
    assert payload["logger"] == "mlops_videos.test"
    assert payload["message"] == "scene_started"


def test_structured_formatter_includes_extra_fields() -> None:
    record = logging.LogRecord(
        name="mlops_videos.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="beat_rendered",
        args=(),
        exc_info=None,
    )
    record.concept = "crisp-dm"
    record.beat = 3
    payload = json.loads(StructuredFormatter().format(record))
    assert payload["concept"] == "crisp-dm"
    assert payload["beat"] == 3
