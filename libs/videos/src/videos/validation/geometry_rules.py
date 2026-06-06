from __future__ import annotations

from typing import Any


class OverlapDetector:
    def check_overlap(self, obj_a: Any, obj_b: Any) -> bool:
        """
        Check if two Manim mobjects overlap using their bounding boxes.
        Bounding box is defined by Down-Left (DL) and Up-Right (UR) corners.
        """
        # Manim directions: DL = [-1, -1, 0], UR = [1, 1, 0]
        dl_a = obj_a.get_corner([-1, -1, 0])
        ur_a = obj_a.get_corner([1, 1, 0])

        dl_b = obj_b.get_corner([-1, -1, 0])
        ur_b = obj_b.get_corner([1, 1, 0])

        # Intersection logic for 2D rectangles in the XY plane
        # Rect A: [dl_a[0], ur_a[0]] x [dl_a[1], ur_a[1]]
        # Rect B: [dl_b[0], ur_b[0]] x [dl_b[1], ur_b[1]]

        # No overlap if one rectangle is to the left of the other
        if ur_a[0] <= dl_b[0] or ur_b[0] <= dl_a[0]:
            return False

        # No overlap if one rectangle is above the other
        if ur_a[1] <= dl_b[1] or ur_b[1] <= dl_a[1]:
            return False

        return True
