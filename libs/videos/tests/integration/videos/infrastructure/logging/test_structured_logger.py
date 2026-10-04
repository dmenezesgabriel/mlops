import json
import logging
import sys
from collections.abc import Iterator

import pytest
from videos.infrastructure.logging.structured_logger import (
    StructuredFormatter,
    setup_structured_logging,
)


@pytest.fixture
def videos_logger() -> Iterator[logging.Logger]:
    logger = logging.getLogger("videos")
    saved_handlers = logger.handlers[:]
    saved_level = logger.level
    saved_propagate = logger.propagate
    logger.handlers.clear()
    try:
        yield logger
    finally:
        logger.handlers[:] = saved_handlers
        logger.setLevel(saved_level)
        logger.propagate = saved_propagate


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


def test_structured_formatter_serializes_exc_info() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        exc_info = sys.exc_info()
    record = logging.LogRecord(
        name="videos.test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="render_failed",
        args=(),
        exc_info=exc_info,
    )
    payload = json.loads(StructuredFormatter().format(record))
    assert "ValueError: boom" in payload["exception"]
    assert "Traceback" in payload["exception"]


def test_setup_is_idempotent(
    videos_logger: logging.Logger, capsys: pytest.CaptureFixture[str]
) -> None:
    # cli.main() calls this on every run — repeat calls must not pile up
    # duplicate handlers on the shared "videos" logger.
    setup_structured_logging()
    setup_structured_logging()
    setup_structured_logging()

    assert len(videos_logger.handlers) == 1

    videos_logger.info("emitted_once")
    assert capsys.readouterr().out.count("emitted_once") == 1


def test_setup_reapplies_level_on_repeat_call(
    videos_logger: logging.Logger,
) -> None:
    setup_structured_logging(logging.INFO)
    setup_structured_logging(logging.WARNING)

    assert len(videos_logger.handlers) == 1
    assert videos_logger.level == logging.WARNING
