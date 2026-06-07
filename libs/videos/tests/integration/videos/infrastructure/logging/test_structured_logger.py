import json
import logging

from videos.infrastructure.logging.structured_logger import StructuredFormatter


def test_structured_formatter_includes_basic_fields() -> None:
    record = logging.LogRecord(
        name="videos.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="scene_started",
        args=(),
        exc_info=None,
    )
    payload = json.loads(StructuredFormatter().format(record))
    assert payload["level"] == "INFO"
    assert payload["logger"] == "videos.test"
    assert payload["message"] == "scene_started"


def test_structured_formatter_includes_video_fields() -> None:
    record = logging.LogRecord(
        name="videos.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="render_complete",
        args=(),
        exc_info=None,
    )
    record.concept_id = "crisp_dm"
    record.scene_id = "scene_1"
    record.correlation_id = "corr_123"
    payload = json.loads(StructuredFormatter().format(record))
    assert payload["concept_id"] == "crisp_dm"
    assert payload["scene_id"] == "scene_1"
    assert payload["correlation_id"] == "corr_123"
