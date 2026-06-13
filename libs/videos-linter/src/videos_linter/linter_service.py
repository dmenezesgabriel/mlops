from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np
from videos.domain.quality import RuleViolation


class ContrastChecker:
    def __init__(self, min_ratio: float = 4.5) -> None:
        self._min_ratio = min_ratio

    def check_image(
        self, image_path: Path, scene_id: str = "unknown"
    ) -> list[RuleViolation]:
        img = cv2.imread(str(image_path))
        if img is None:
            return []

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Threshold: assume dark background (around 30).
        # We can find contours with intensity above threshold 40.
        _, thresh = cv2.threshold(gray, 40, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        violations = []
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
            fg_mean = np.mean(fg_pixels, axis=0)

            if np.any(bg_mask):
                bg_pixels = roi_bgr[bg_mask]
                bg_mean = np.mean(bg_pixels, axis=0)
            else:
                bg_mean = np.array([30.0, 30.0, 30.0])

            fg_b, fg_g, fg_r = (
                fg_mean[0] / 255.0,
                fg_mean[1] / 255.0,
                fg_mean[2] / 255.0,
            )
            bg_b, bg_g, bg_r = (
                bg_mean[0] / 255.0,
                bg_mean[1] / 255.0,
                bg_mean[2] / 255.0,
            )

            l_fg = 0.2126 * fg_r + 0.7152 * fg_g + 0.0722 * fg_b
            l_bg = 0.2126 * bg_r + 0.7152 * bg_g + 0.0722 * bg_b

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
        img = cv2.imread(str(image_path))
        if img is None:
            return []

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


class ImageOverlapDetector:
    def check_image(
        self, image_path: Path, scene_id: str = "unknown"
    ) -> list[RuleViolation]:
        img = cv2.imread(str(image_path))
        if img is None:
            return []

        boxes: list[tuple[int, int, int, int]] = []
        channels = list(cv2.split(img)) + [
            cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        ]
        for ch in channels:
            _, thresh = cv2.threshold(ch, 40, 255, cv2.THRESH_BINARY)
            contours, _ = cv2.findContours(
                thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                if w < 5 or h < 5:
                    continue
                is_duplicate = False
                for bx, by, bw, bh in boxes:
                    if (
                        abs(x - bx) < 3
                        and abs(y - by) < 3
                        and abs(w - bw) < 3
                        and abs(h - bh) < 3
                    ):
                        is_duplicate = True
                        break
                if not is_duplicate:
                    boxes.append((x, y, w, h))

        violations = []
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                x_a, y_a, w_a, h_a = boxes[i]
                x_b, y_b, w_b, h_b = boxes[j]

                x_left = max(x_a, x_b)
                y_top = max(y_a, y_b)
                x_right = min(x_a + w_a, x_b + w_b)
                y_bottom = min(y_a + h_a, y_b + h_b)

                if x_right > x_left and y_bottom > y_top:
                    intersection_area = (x_right - x_left) * (y_bottom - y_top)
                    if intersection_area > 10:
                        violations.append(
                            RuleViolation(
                                scene_id=scene_id,
                                rule="visual_overlap",
                                suggestion=(
                                    f"Rendered elements overlap in image space. "
                                    f"Overlap area of {intersection_area} pixels detected "
                                    f"between element {i} and element {j}."
                                ),
                                object_id=f"elements_{i}_{j}",
                                actual=f"overlap_area={intersection_area}",
                                expected="no overlap",
                            )
                        )
        return violations


class VideoMotionAnalyzer:
    def __init__(
        self,
        max_frozen_seconds: float = 2.0,
        stutter_threshold: float = 80.0,
    ) -> None:
        self._max_frozen_seconds = max_frozen_seconds
        self._stutter_threshold = stutter_threshold

    def analyze_video(
        self, video_path: Path, scene_id: str = "unknown"
    ) -> list[RuleViolation]:
        import math

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return []

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 30.0

        frame_brightnesses: list[float] = []
        frame_diffs: list[float] = []
        centroids: list[tuple[int, int] | None] = []

        ret, prev_frame = cap.read()
        if not ret:
            cap.release()
            return []

        prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
        frame_brightnesses.append(float(np.mean(prev_gray)))

        _, prev_thresh = cv2.threshold(prev_gray, 40, 255, cv2.THRESH_BINARY)
        moments = cv2.moments(prev_thresh)
        if moments["m00"] > 0:
            prev_cx = int(moments["m10"] / moments["m00"])
            prev_cy = int(moments["m01"] / moments["m00"])
            centroids.append((prev_cx, prev_cy))
        else:
            centroids.append(None)

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            frame_brightnesses.append(float(np.mean(gray)))

            diff = cv2.absdiff(gray, prev_gray)
            diff_mean = float(np.mean(diff))
            frame_diffs.append(diff_mean)

            _, thresh = cv2.threshold(gray, 40, 255, cv2.THRESH_BINARY)
            moments = cv2.moments(thresh)
            if moments["m00"] > 0:
                cx = int(moments["m10"] / moments["m00"])
                cy = int(moments["m01"] / moments["m00"])
                centroids.append((cx, cy))
            else:
                centroids.append(None)

            prev_gray = gray

        cap.release()

        violations = []
        num_frames = len(frame_brightnesses)
        if num_frames < 2:
            return []

        consecutive_frozen = 0
        max_consecutive_frozen = 0
        for diff_val in frame_diffs:
            if diff_val < 0.05:
                consecutive_frozen += 1
                if consecutive_frozen > max_consecutive_frozen:
                    max_consecutive_frozen = consecutive_frozen
            else:
                consecutive_frozen = 0

        frozen_seconds = max_consecutive_frozen / fps
        if frozen_seconds > self._max_frozen_seconds:
            violations.append(
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
            )

        flicker_count = 0
        for i in range(2, num_frames):
            diff1 = frame_brightnesses[i] - frame_brightnesses[i - 1]
            diff2 = frame_brightnesses[i - 1] - frame_brightnesses[i - 2]
            if abs(diff1) > 10.0 and abs(diff2) > 10.0:
                if (diff1 > 0 and diff2 < 0) or (diff1 < 0 and diff2 > 0):
                    flicker_count += 1

        flicker_ratio = flicker_count / num_frames
        if flicker_ratio > 0.1:
            violations.append(
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
            )

        for i in range(1, num_frames):
            c_curr = centroids[i]
            c_prev = centroids[i - 1]
            if c_curr is not None and c_prev is not None:
                dist = math.sqrt(
                    (c_curr[0] - c_prev[0]) ** 2 + (c_curr[1] - c_prev[1]) ** 2
                )
                if dist > self._stutter_threshold:
                    violations.append(
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
                    )
                    break

        return violations


class LinterError(RuntimeError):
    pass


class LinterService:
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

    def verify_geometry(
        self, mobjects: list[Any], scene_id: str
    ) -> list[RuleViolation]:
        from videos.infrastructure.validation.geometry_rules import (
            OverlapDetector,
        )

        detector = OverlapDetector()
        violations = []
        for i in range(len(mobjects)):
            for j in range(i + 1, len(mobjects)):
                if detector.check_overlap(mobjects[i], mobjects[j]):
                    violations.append(
                        RuleViolation(
                            scene_id=scene_id,
                            rule="geometric_overlap",
                            suggestion="Adjust layout coordinates to prevent overlapping elements.",
                            actual=f"Overlap between object {i} and {j}",
                        )
                    )
        return violations

    def verify_visuals(self, image_path: Path, scene_id: str) -> None:
        violations = self._contrast_checker.check_image(image_path, scene_id)
        if violations:
            raise LinterError(
                f"Visual Linter failed for scene {scene_id!r} due to contrast issues: "
                + "; ".join(v.suggestion for v in violations)
            )

        violations = self._blur_detector.check_image(image_path, scene_id)
        if violations:
            raise LinterError(
                f"Visual Linter failed for scene {scene_id!r} due to blurriness: "
                + "; ".join(v.suggestion for v in violations)
            )

        violations = self._overlap_detector.check_image(image_path, scene_id)
        if violations:
            raise LinterError(
                f"Visual Linter failed for scene {scene_id!r} due to overlapping elements: "
                + "; ".join(v.suggestion for v in violations)
            )

    def verify_video(self, video_path: Path, scene_id: str) -> None:
        violations = self._motion_analyzer.analyze_video(video_path, scene_id)
        if violations:
            raise LinterError(
                f"Video Linter failed for scene {scene_id!r} due to motion issues: "
                + "; ".join(v.suggestion for v in violations)
            )
