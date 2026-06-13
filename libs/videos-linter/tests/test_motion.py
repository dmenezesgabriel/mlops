from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest
from videos_linter.linter_service import VideoMotionAnalyzer


@pytest.fixture
def temp_video_dir(tmp_path: Path) -> Path:
    return tmp_path


def _create_video(
    path: Path,
    num_frames: int,
    fps: int,
    generator,
) -> Path:
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, fps, (200, 200))
    for i in range(num_frames):
        frame = generator(i)
        writer.write(frame)
    writer.release()
    return path


class TestVideoMotionAnalyzer:
    def test_passes_on_smooth_motion(self, temp_video_dir: Path) -> None:
        # A box moves smoothly (5 pixels per frame)
        def smooth_gen(frame_idx: int) -> np.ndarray:
            img = np.full((200, 200, 3), 30, dtype=np.uint8)
            x = 10 + frame_idx * 2
            cv2.rectangle(img, (x, 80), (x + 30, 120), (255, 255, 255), -1)
            return img

        video_path = _create_video(
            temp_video_dir / "smooth.mp4", 30, 30, smooth_gen
        )
        analyzer = VideoMotionAnalyzer()
        violations = analyzer.analyze_video(video_path)
        assert len(violations) == 0

    def test_detects_frozen_video(self, temp_video_dir: Path) -> None:
        # A box moves for first 5 frames, then freezes for 45 frames (1.5 seconds at 30 fps)
        def frozen_gen(frame_idx: int) -> np.ndarray:
            img = np.full((200, 200, 3), 30, dtype=np.uint8)
            x = 10 + min(frame_idx, 5) * 5
            cv2.rectangle(img, (x, 80), (x + 30, 120), (255, 255, 255), -1)
            return img

        video_path = _create_video(
            temp_video_dir / "frozen.mp4", 50, 30, frozen_gen
        )
        # Set frozen threshold to 1.0 second
        analyzer = VideoMotionAnalyzer(max_frozen_seconds=1.0)
        violations = analyzer.analyze_video(video_path)
        assert len(violations) > 0
        assert any("frozen" in v.rule for v in violations)

    def test_detects_flickering(self, temp_video_dir: Path) -> None:
        # Frame intensity alternates between 30 and 180 every frame (high frequency flicker)
        def flicker_gen(frame_idx: int) -> np.ndarray:
            val = 30 if frame_idx % 2 == 0 else 180
            return np.full((200, 200, 3), val, dtype=np.uint8)

        video_path = _create_video(
            temp_video_dir / "flicker.mp4", 30, 30, flicker_gen
        )
        analyzer = VideoMotionAnalyzer()
        violations = analyzer.analyze_video(video_path)
        assert len(violations) > 0
        assert any("flicker" in v.rule for v in violations)

    def test_detects_stutter_jump(self, temp_video_dir: Path) -> None:
        # Box moves smoothly, but has a sudden massive jump of 100 pixels in frame 15
        def jump_gen(frame_idx: int) -> np.ndarray:
            img = np.full((200, 200, 3), 30, dtype=np.uint8)
            if frame_idx < 15:
                x = 10 + frame_idx * 2
            else:
                x = 10 + frame_idx * 2 + 100
            cv2.rectangle(img, (x, 80), (x + 30, 120), (255, 255, 255), -1)
            return img

        video_path = _create_video(
            temp_video_dir / "jump.mp4", 30, 30, jump_gen
        )
        analyzer = VideoMotionAnalyzer(stutter_threshold=80.0)
        violations = analyzer.analyze_video(video_path)
        assert len(violations) > 0
        assert any("stutter" in v.rule or "jump" in v.rule for v in violations)
