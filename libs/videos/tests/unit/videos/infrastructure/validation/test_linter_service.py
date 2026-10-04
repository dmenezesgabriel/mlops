from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image
from videos.infrastructure.validation.linter_service import (
    LinterError,
    LinterService,
)

# Minimal ISO-BMFF header — the local fallback has no cv2, so "decodable" is
# proven by the first box being `ftyp` (every resolved artifact is .mp4).
_FAKE_MP4_BYTES = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 16


class TestVerifyVideo:
    def test_missing_video_raises(self, tmp_path: Path) -> None:
        service = LinterService()

        with pytest.raises(LinterError, match="scene_1"):
            service.verify_video(tmp_path / "absent.mp4", "scene_1")

    @pytest.mark.parametrize(
        "payload",
        [b"", b"not a video file", b"\x00" * 64, b"\x00\x00\x00\x10free1234"],
    )
    def test_undecodable_video_raises(
        self, tmp_path: Path, payload: bytes
    ) -> None:
        video = tmp_path / "broken.mp4"
        video.write_bytes(payload)
        service = LinterService()

        with pytest.raises(LinterError, match="scene_1"):
            service.verify_video(video, "scene_1")

    def test_mp4_with_ftyp_header_passes(self, tmp_path: Path) -> None:
        video = tmp_path / "ok.mp4"
        video.write_bytes(_FAKE_MP4_BYTES)
        service = LinterService()

        service.verify_video(video, "scene_1")


class TestVerifyVisuals:
    def test_blank_frame_raises(self, tmp_path: Path) -> None:
        # Manim background (30,30,30) with zero content — a failed render,
        # not a passing layout.
        path = tmp_path / "blank.png"
        Image.new("RGB", (854, 480), color=(30, 30, 30)).save(path)
        service = LinterService()

        with pytest.raises(LinterError, match="blank"):
            service.verify_visuals(path, "scene_1")
