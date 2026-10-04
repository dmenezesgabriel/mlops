from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from videos.application.ports.linter import Linter
from videos.domain.quality import RuleViolation

Box = tuple[int, int, int, int]


def _read_image(img_path: Path) -> np.ndarray | None:
    img = cv2.imread(str(img_path))
    if img is None:
        return None
    return img


def _unreadable_image_violation(
    image_path: Path, scene_id: str
) -> RuleViolation:
    return RuleViolation(
        scene_id=scene_id,
        rule="unreadable_image",
        suggestion=(
            f"Could not decode image at '{image_path}'. "
            f"Expected a readable image file."
        ),
        actual="missing or undecodable",
        expected="a decodable image file",
    )


def _unreadable_video_violation(
    video_path: Path, scene_id: str, detail: str
) -> RuleViolation:
    return RuleViolation(
        scene_id=scene_id,
        rule="unreadable_video",
        suggestion=f"Could not analyze video at '{video_path}': {detail}.",
        actual=detail,
        expected="a decodable video with >= 2 frames",
    )


def _frame_centroid(gray: np.ndarray) -> tuple[int, int] | None:
    _, thresh = cv2.threshold(gray, 40, 255, cv2.THRESH_BINARY)
    moments = cv2.moments(thresh)
    if moments["m00"] <= 0:
        return None
    return int(moments["m10"] / moments["m00"]), int(
        moments["m01"] / moments["m00"]
    )


def _relative_luminance(mean_bgr: np.ndarray) -> float:
    # WCAG 2.x contrast math runs on linear-light luminance: each sRGB
    # channel must be linearized before the Rec. 709 coefficients, or the
    # ratio lands ~3x too strict at the dark end and false-rejects
    # AA-conformant pairs.
    srgb = mean_bgr / 255.0
    linear = np.where(
        srgb <= 0.04045, srgb / 12.92, ((srgb + 0.055) / 1.055) ** 2.4
    )
    return float(0.0722 * linear[0] + 0.7152 * linear[1] + 0.2126 * linear[2])


class ContrastChecker:
    def __init__(self, min_ratio: float = 4.5) -> None:
        self._min_ratio = min_ratio

    def check_image(
        self, image_path: Path, scene_id: str = "unknown"
    ) -> list[RuleViolation]:
        img = _read_image(image_path)
        if img is None:
            return [_unreadable_image_violation(image_path, scene_id)]

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Threshold: assume dark background (around 30).
        # We can find contours with intensity above threshold 40.
        _, thresh = cv2.threshold(gray, 40, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        violations: list[RuleViolation] = []
        for idx, contour in enumerate(contours):
            x, y, w, h = cv2.boundingRect(contour)
            # Ignore extremely small noise
            if w < 5 or h < 5:
                continue

            roi_gray = gray[y : y + h, x : x + w]
            roi_bgr = img[y : y + h, x : x + w]

            fg_mask = roi_gray > 40
            bg_mask = ~fg_mask

            if not np.any(fg_mask):
                continue

            fg_pixels = roi_bgr[fg_mask]
            fg_mean = np.percentile(fg_pixels, 95, axis=0)

            if np.any(bg_mask):
                bg_pixels = roi_bgr[bg_mask]
                bg_mean = np.percentile(bg_pixels, 5, axis=0)
            else:
                # No sub-threshold pixels inside the contour's bounding box:
                # measure the image's own dark end rather than assume a fixed
                # background — a bright slide would otherwise pass against a
                # phantom dark floor.
                bg_mean = np.percentile(img.reshape(-1, 3), 5, axis=0)

            l_fg = _relative_luminance(fg_mean)
            l_bg = _relative_luminance(bg_mean)

            l_lightest = max(l_fg, l_bg)
            l_darkest = min(l_fg, l_bg)

            ratio = (l_lightest + 0.05) / (l_darkest + 0.05)

            if ratio < self._min_ratio:
                violations.append(
                    RuleViolation(
                        scene_id=scene_id,
                        rule="insufficient_text_contrast",
                        suggestion=(
                            f"Increase contrast between elements and background. "
                            f"Got contrast ratio {ratio:.2f}, expected >= {self._min_ratio}."
                        ),
                        object_id=f"element_{idx}",
                        actual=f"{ratio:.2f}",
                        expected=f">= {self._min_ratio}",
                    )
                )
        return violations


class BlurDetector:
    def __init__(self, threshold: float = 100.0) -> None:
        self._threshold = threshold

    def check_image(
        self, image_path: Path, scene_id: str = "unknown"
    ) -> list[RuleViolation]:
        img = _read_image(image_path)
        if img is None:
            return [_unreadable_image_violation(image_path, scene_id)]

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        variance = cv2.Laplacian(gray, cv2.CV_64F).var()

        if variance < self._threshold:
            return [
                RuleViolation(
                    scene_id=scene_id,
                    rule="blurry_image",
                    suggestion=(
                        f"Image resolution or rendering is blurry/out of focus. "
                        f"Laplacian variance {variance:.2f} is below threshold {self._threshold}."
                    ),
                    actual=f"{variance:.2f}",
                    expected=f">= {self._threshold}",
                )
            ]
        return []


# A concavity this deep in a thresholded blob means several same-color
# elements fused into one contour — glyph-level notches (kerning) stay well
# under it after the 20px dilation smooths them out.
_MERGED_BLOB_DEFECT_DEPTH = 25.0


@dataclass(frozen=True)
class _DetectedBlob:
    box: Box
    deepest_defect: float


def _deepest_defect_depth(contour: np.ndarray) -> float:
    if len(contour) < 3:
        return 0.0
    hull = cv2.convexHull(contour, returnPoints=False)
    if hull is None or len(hull) <= 3:
        return 0.0
    defects = cv2.convexityDefects(contour, hull)
    if defects is None:
        return 0.0
    # cv2 reports defect depth in 8.24 fixed-point units.
    return float(max(d[0][3] for d in defects) / 256.0)


def _detect_boxes(img: np.ndarray) -> list[_DetectedBlob]:
    channels = list(cv2.split(img)) + [cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)]
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 20))
    blobs: list[_DetectedBlob] = []
    for ch in channels:
        _collect_channel_boxes(ch, kernel, blobs)
    return blobs


def _collect_channel_boxes(
    ch: np.ndarray, kernel: np.ndarray, blobs: list[_DetectedBlob]
) -> None:
    _, thresh = cv2.threshold(ch, 40, 255, cv2.THRESH_BINARY)
    thresh = cv2.dilate(thresh, kernel, iterations=1)
    contours, _ = cv2.findContours(
        thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        # Ignore extremely small noise
        if w < 5 or h < 5:
            continue
        box = (x, y, w, h)
        if not _is_known_box(box, blobs):
            blobs.append(
                _DetectedBlob(
                    box=box, deepest_defect=_deepest_defect_depth(contour)
                )
            )


def _is_known_box(box: Box, blobs: list[_DetectedBlob]) -> bool:
    x, y, w, h = box
    return any(
        abs(x - b.box[0]) < 3
        and abs(y - b.box[1]) < 3
        and abs(w - b.box[2]) < 3
        and abs(h - b.box[3]) < 3
        for b in blobs
    )


def _intersection_area(a: Box, b: Box) -> int:
    x_right = min(a[0] + a[2], b[0] + b[2])
    y_bottom = min(a[1] + a[3], b[1] + b[3])
    width = x_right - max(a[0], b[0])
    height = y_bottom - max(a[1], b[1])
    if width <= 0 or height <= 0:
        return 0
    return width * height


class ImageOverlapDetector:
    def check_image(
        self, image_path: Path, scene_id: str = "unknown"
    ) -> list[RuleViolation]:
        img = _read_image(image_path)
        if img is None:
            return [_unreadable_image_violation(image_path, scene_id)]
        return self._overlap_violations(_detect_boxes(img), scene_id)

    def _overlap_violations(
        self, blobs: list[_DetectedBlob], scene_id: str
    ) -> list[RuleViolation]:
        violations: list[RuleViolation] = []
        for i, blob_a in enumerate(blobs):
            if blob_a.deepest_defect >= _MERGED_BLOB_DEFECT_DEPTH:
                violations.append(_merged_blob_violation(blob_a, scene_id, i))
            for j, blob_b in enumerate(blobs[i + 1 :], start=i + 1):
                violation = _overlap_violation(
                    blob_a.box, blob_b.box, scene_id, i, j
                )
                if violation is not None:
                    violations.append(violation)
        return violations


def _merged_blob_violation(
    blob: _DetectedBlob, scene_id: str, idx: int
) -> RuleViolation:
    return RuleViolation(
        scene_id=scene_id,
        rule="visual_overlap",
        suggestion=(
            f"Rendered elements overlap in image space. "
            f"Element {idx} is a fused blob with a "
            f"{blob.deepest_defect:.1f}px concavity — overlapping "
            f"same-color elements merged into one region."
        ),
        object_id=f"element_{idx}",
        actual=f"concavity={blob.deepest_defect:.1f}px",
        expected="no overlap",
    )


def _overlap_violation(
    box_a: Box, box_b: Box, scene_id: str, i: int, j: int
) -> RuleViolation | None:
    area = _intersection_area(box_a, box_b)
    if area <= 10:
        return None
    min_area = min(box_a[2] * box_a[3], box_b[2] * box_b[3])
    # Skip almost identical or heavily nested boxes (channel duplicates):
    # intersection covers >0.7 of the smaller box.
    if min_area > 0 and area / min_area > 0.7:
        return None
    return RuleViolation(
        scene_id=scene_id,
        rule="visual_overlap",
        suggestion=(
            f"Rendered elements overlap in image space. "
            f"Overlap area of {area} pixels detected "
            f"between element {i} and element {j}."
        ),
        object_id=f"elements_{i}_{j}",
        actual=f"overlap_area={area}",
        expected="no overlap",
    )


@dataclass
class _FrameStats:
    fps: float
    brightnesses: list[float]
    diffs: list[float]
    centroids: list[tuple[int, int] | None]


def _collect_frame_stats(cap: cv2.VideoCapture) -> _FrameStats | None:
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30.0

    ret, frame = cap.read()
    if not ret:
        return None

    prev_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    brightnesses = [float(np.mean(prev_gray))]
    diffs: list[float] = []
    centroids = [_frame_centroid(prev_gray)]

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        brightnesses.append(float(np.mean(gray)))
        diffs.append(float(np.mean(cv2.absdiff(gray, prev_gray))))
        centroids.append(_frame_centroid(gray))
        prev_gray = gray

    if len(brightnesses) < 2:
        return None
    return _FrameStats(fps, brightnesses, diffs, centroids)


def _longest_frozen_run(diffs: list[float]) -> int:
    longest = current = 0
    for diff_val in diffs:
        if diff_val >= 0.05:
            current = 0
            continue
        current += 1
        longest = max(longest, current)
    return longest


def _is_brightness_sign_flip(before: float, mid: float, after: float) -> bool:
    diff1 = after - mid
    diff2 = mid - before
    if abs(diff1) <= 10.0 or abs(diff2) <= 10.0:
        return False
    return (diff1 > 0) != (diff2 > 0)


def _first_jump_distance(
    centroids: list[tuple[int, int] | None], threshold: float
) -> float | None:
    # Adjacent pairs: the offset slice is one shorter by design.
    for prev, curr in zip(centroids, centroids[1:], strict=False):
        if curr is None or prev is None:
            continue
        dist = math.hypot(curr[0] - prev[0], curr[1] - prev[1])
        if dist > threshold:
            return dist
    return None


class VideoMotionAnalyzer:
    def __init__(
        self,
        max_frozen_seconds: float = 15.0,
        stutter_threshold: float = 80.0,
    ) -> None:
        self._max_frozen_seconds = max_frozen_seconds
        self._stutter_threshold = stutter_threshold

    def analyze_video(
        self, video_path: Path, scene_id: str = "unknown"
    ) -> list[RuleViolation]:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return [
                _unreadable_video_violation(
                    video_path, scene_id, "video failed to open"
                )
            ]
        try:
            stats = _collect_frame_stats(cap)
        finally:
            cap.release()
        if stats is None:
            return [
                _unreadable_video_violation(
                    video_path, scene_id, "fewer than 2 decodable frames"
                )
            ]
        violations = self._check_frozen(stats, scene_id)
        violations += self._check_flicker(stats, scene_id)
        violations += self._check_stutter(stats, scene_id)
        return violations

    def _check_frozen(
        self, stats: _FrameStats, scene_id: str
    ) -> list[RuleViolation]:
        frozen_seconds = _longest_frozen_run(stats.diffs) / stats.fps
        if frozen_seconds <= self._max_frozen_seconds:
            return []
        return [
            RuleViolation(
                scene_id=scene_id,
                rule="frozen_video",
                suggestion=(
                    f"Video animation is frozen for too long. "
                    f"Detected frozen segment of {frozen_seconds:.2f}s, expected <= {self._max_frozen_seconds}s."
                ),
                actual=f"{frozen_seconds:.2f}s",
                expected=f"<= {self._max_frozen_seconds}s",
            )
        ]

    def _check_flicker(
        self, stats: _FrameStats, scene_id: str
    ) -> list[RuleViolation]:
        brightnesses = stats.brightnesses
        flicker_count = sum(
            1
            for i in range(2, len(brightnesses))
            if _is_brightness_sign_flip(
                brightnesses[i - 2], brightnesses[i - 1], brightnesses[i]
            )
        )
        flicker_ratio = flicker_count / len(brightnesses)
        if flicker_ratio <= 0.1:
            return []
        return [
            RuleViolation(
                scene_id=scene_id,
                rule="video_flicker",
                suggestion=(
                    f"High-frequency brightness flickering detected. "
                    f"Flicker ratio {flicker_ratio * 100:.1f}% exceeds safe limit of 10%."
                ),
                actual=f"{flicker_ratio * 100:.1f}%",
                expected="<= 10%",
            )
        ]

    def _check_stutter(
        self, stats: _FrameStats, scene_id: str
    ) -> list[RuleViolation]:
        dist = _first_jump_distance(stats.centroids, self._stutter_threshold)
        if dist is None:
            return []
        return [
            RuleViolation(
                scene_id=scene_id,
                rule="video_stutter_jump",
                suggestion=(
                    f"Sudden jump or stutter detected in video animation. "
                    f"Centroid displacement of {dist:.2f} pixels exceeds threshold {self._stutter_threshold}."
                ),
                actual=f"{dist:.2f} pixels",
                expected=f"<= {self._stutter_threshold} pixels",
            )
        ]


class LinterError(RuntimeError):
    pass


class LinterService(Linter):
    def __init__(
        self,
        contrast_checker: ContrastChecker | None = None,
        blur_detector: BlurDetector | None = None,
        overlap_detector: ImageOverlapDetector | None = None,
        motion_analyzer: VideoMotionAnalyzer | None = None,
    ) -> None:
        self._contrast_checker = contrast_checker or ContrastChecker()
        self._blur_detector = blur_detector or BlurDetector()
        self._overlap_detector = overlap_detector or ImageOverlapDetector()
        self._motion_analyzer = motion_analyzer or VideoMotionAnalyzer()

    def verify_visuals(self, image_path: Path, scene_id: str) -> None:
        labels: list[str] = []
        suggestions: list[str] = []
        for checker, label in (
            (self._contrast_checker, "contrast issues"),
            (self._blur_detector, "blurriness"),
            (self._overlap_detector, "overlapping elements"),
        ):
            violations = checker.check_image(image_path, scene_id)
            if not violations:
                continue
            labels.append(label)
            for violation in violations:
                # Every checker reports the same unreadable-image violation
                # on a decode failure — emit each distinct suggestion once.
                if violation.suggestion not in suggestions:
                    suggestions.append(violation.suggestion)
        if suggestions:
            raise LinterError(
                f"Visual Linter failed for scene {scene_id!r} due to "
                + ", ".join(labels)
                + ": "
                + "; ".join(suggestions)
            )

    def verify_video(self, video_path: Path, scene_id: str) -> None:
        violations = self._motion_analyzer.analyze_video(video_path, scene_id)
        if violations:
            raise LinterError(
                f"Video Linter failed for scene {scene_id!r} due to motion issues: "
                + "; ".join(v.suggestion for v in violations)
            )
