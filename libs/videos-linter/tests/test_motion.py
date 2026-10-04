from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest
from videos_linter.linter_service import (
    VideoMotionAnalyzer,
    _is_brightness_sign_flip,
)

from tests._fakes import FakeVideoCapture


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

    def test_flags_missing_video(self, temp_video_dir: Path) -> None:
        analyzer = VideoMotionAnalyzer()
        violations = analyzer.analyze_video(temp_video_dir / "missing.mp4")
        assert len(violations) == 1
        assert violations[0].rule == "unreadable_video"

    def test_flags_undecodable_video(self, temp_video_dir: Path) -> None:
        corrupt_path = temp_video_dir / "corrupt.mp4"
        corrupt_path.write_bytes(b"this is not video data")
        analyzer = VideoMotionAnalyzer()
        violations = analyzer.analyze_video(corrupt_path)
        assert len(violations) == 1
        assert violations[0].rule == "unreadable_video"

    def test_flags_video_with_too_few_frames(
        self, temp_video_dir: Path
    ) -> None:
        def still_gen(frame_idx: int) -> np.ndarray:
            return np.full((200, 200, 3), 30, dtype=np.uint8)

        video_path = _create_video(
            temp_video_dir / "one_frame.mp4", 1, 30, still_gen
        )
        analyzer = VideoMotionAnalyzer()
        violations = analyzer.analyze_video(video_path)
        assert len(violations) == 1
        assert violations[0].rule == "unreadable_video"

    def test_flags_video_whose_first_frame_read_fails(
        self, temp_video_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_cap = FakeVideoCapture(frames=[])
        _use_fake_capture(monkeypatch, fake_cap)
        analyzer = VideoMotionAnalyzer()
        violations = analyzer.analyze_video(temp_video_dir / "empty.mp4")
        assert [v.rule for v in violations] == ["unreadable_video"]
        assert fake_cap.released is True

    def test_falls_back_to_30fps_when_fps_unreadable(
        self, temp_video_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # fps<=0 must default to 30 — otherwise frozen_seconds divides by 0.
        frames = [_uniform_frame(30) for _ in range(20)]
        fake_cap = FakeVideoCapture(frames=frames, fps=0.0)
        _use_fake_capture(monkeypatch, fake_cap)
        analyzer = VideoMotionAnalyzer(max_frozen_seconds=0.5)
        violations = analyzer.analyze_video(temp_video_dir / "frozen.mp4")
        assert [v.rule for v in violations] == ["frozen_video"]


def _use_fake_capture(
    monkeypatch: pytest.MonkeyPatch, fake_cap: FakeVideoCapture
) -> None:
    def capture_factory(_path: str) -> FakeVideoCapture:
        return fake_cap

    monkeypatch.setattr(
        "videos_linter.linter_service.cv2.VideoCapture", capture_factory
    )


def _uniform_frame(value: int) -> np.ndarray:
    return np.full((200, 200, 3), value, dtype=np.uint8)


def _block_frame(x: int) -> np.ndarray:
    frame = _uniform_frame(30)
    frame[80:120, x : x + 40] = 255
    return frame


class TestMotionCheckBoundaries:
    """Pin the exact relational thresholds through `analyze_video` — a
    flipped operator must change the observable result."""

    def test_frozen_run_breaks_on_diff_at_exactly_0_05(
        self, temp_video_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A mean absdiff of exactly 0.05 counts as motion — the frozen
        # counter must reset, not accumulate. Alternating frames where
        # 2000 of 40000 pixels differ by 1 gives a mean diff of exactly
        # 0.05 on every consecutive pair.
        base = _uniform_frame(30)
        dev = base.copy()
        dev[:10, :] = 31
        frames = [base.copy() if i % 2 == 0 else dev.copy() for i in range(21)]
        _use_fake_capture(monkeypatch, FakeVideoCapture(frames=frames))

        analyzer = VideoMotionAnalyzer(max_frozen_seconds=0.5)
        violations = analyzer.analyze_video(temp_video_dir / "boundary.mp4")
        assert violations == []

    def test_flicker_ratio_at_exactly_10_percent_passes(
        self, temp_video_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # 2 sign flips in 20 frames lands exactly on the 0.1 limit — not
        # over it.
        brightnesses = [30, 180, 30, 30, 30, 180, 30] + [30] * 13
        frames = [_uniform_frame(v) for v in brightnesses]
        _use_fake_capture(monkeypatch, FakeVideoCapture(frames=frames))

        analyzer = VideoMotionAnalyzer()
        violations = analyzer.analyze_video(temp_video_dir / "boundary.mp4")
        assert violations == []

    def test_stutter_jump_at_exactly_threshold_is_not_flagged(
        self, temp_video_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A centroid displacement of exactly the threshold must not flag —
        # the check is strictly greater-than.
        frames = [_block_frame(10), _block_frame(90)]
        _use_fake_capture(monkeypatch, FakeVideoCapture(frames=frames))

        analyzer = VideoMotionAnalyzer(stutter_threshold=80.0)
        violations = analyzer.analyze_video(temp_video_dir / "boundary.mp4")
        assert violations == []

    def test_stutter_jump_just_over_threshold_is_flagged(
        self, temp_video_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        frames = [_block_frame(10), _block_frame(91)]
        _use_fake_capture(monkeypatch, FakeVideoCapture(frames=frames))

        analyzer = VideoMotionAnalyzer(stutter_threshold=80.0)
        violations = analyzer.analyze_video(temp_video_dir / "jump.mp4")
        assert [v.rule for v in violations] == ["video_stutter_jump"]

    @pytest.mark.parametrize(
        "before,mid,after",
        [
            (200.0, 150.0, 160.0),  # |after-mid| == 10 exactly
            (20.0, 150.0, 140.0),  # |after-mid| == 10, negative side
            (140.0, 150.0, 100.0),  # |mid-before| == 10 exactly
            (160.0, 150.0, 200.0),  # |mid-before| == 10, negative side
        ],
    )
    def test_brightness_delta_of_exactly_10_is_not_a_flip(
        self, before: float, mid: float, after: float
    ) -> None:
        # A one-sided delta at the 10.0 noise bound must not count — the
        # check requires BOTH deltas to clear 10.
        assert _is_brightness_sign_flip(before, mid, after) is False

    def test_brightness_sign_flip_detected_when_both_deltas_clear_10(
        self,
    ) -> None:
        assert _is_brightness_sign_flip(30.0, 180.0, 30.0) is True
