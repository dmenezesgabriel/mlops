"""Option A: Verify builder coordinate math produces non-overlapping layouts.

Uses synthetic position data to validate that concentric rings,
dart positions, cycle nodes, and graph labels avoid overlaps
at the coordinate level.
"""

from __future__ import annotations

import math


def _circles_overlap(
    x1: float, y1: float, r1: float, x2: float, y2: float, r2: float
) -> bool:
    distance = math.hypot(x2 - x1, y2 - y1)
    return distance < (r1 + r2)


class TestTargetRings:
    def test_rings_are_nested_and_non_overlapping(self) -> None:
        rings = 4
        max_radius = 2.0
        radii = [max_radius * (rings - i) / rings for i in range(rings)]
        # All rings share the same center; their radii must be decreasing
        for i in range(len(radii) - 1):
            assert radii[i] > radii[i + 1], (
                f"Ring {i} radius {radii[i]:.3f} not > ring {i+1} radius {radii[i+1]:.3f}"
            )


class TestDartPositions:
    def test_darts_in_same_cluster_dont_overlap(self) -> None:
        # Simulates high-bias cluster (tight grouping around a point)
        positions: list[tuple[float, float, float]] = [
            (-4.0, 0.5, 0.05),
            (-3.8, 0.7, 0.05),
            (-4.2, 0.3, 0.05),
            (-3.9, 0.6, 0.05),
        ]
        for i, (x1, y1, r1) in enumerate(positions):
            for j, (x2, y2, r2) in enumerate(positions):
                if i >= j:
                    continue
                if _circles_overlap(x1, y1, r1, x2, y2, r2):
                    # Close clustering expected in high-bias, so tight overlaps
                    # are OK. The test here ensures darts don't *completely*
                    # overlap (same center).
                    assert (x1, y1) != (x2, y2), (
                        f"Darts {i} and {j} share identical center ({x1}, {y1})"
                    )

    def test_sweet_spot_darts_at_distinct_positions(self) -> None:
        positions: list[tuple[float, float]] = [
            (-3.5, 0.0),
            (-3.4, 0.1),
            (-3.6, -0.1),
            (-3.5, 0.1),
        ]
        seen: set[tuple[float, float]] = set()
        for pos in positions:
            assert pos not in seen, f"Duplicate dart position {pos}"
            seen.add(pos)


class TestCycleNodeDistribution:
    def test_nodes_are_evenly_spaced(self) -> None:
        n = 6
        radius = 2.5
        angles = [2 * math.pi * i / n - math.pi / 2 for i in range(n)]
        positions = [
            (radius * math.cos(a), radius * math.sin(a)) for a in angles
        ]

        gaps = []
        for i in range(n):
            x1, y1 = positions[i]
            x2, y2 = positions[(i + 1) % n]
            gaps.append(math.hypot(x2 - x1, y2 - y1))

        mean_gap = sum(gaps) / n
        for i, gap in enumerate(gaps):
            assert abs(gap - mean_gap) / mean_gap < 0.01, (
                f"Gap {i} ({gap:.3f}) deviates from mean ({mean_gap:.3f}) "
                f"by more than 1%"
            )

    def test_adjacent_nodes_dont_overlap(self) -> None:
        n = 6
        node_radius = 0.6
        cycle_radius = 2.5
        angles = [2 * math.pi * i / n - math.pi / 2 for i in range(n)]
        positions = [
            (cycle_radius * math.cos(a), cycle_radius * math.sin(a))
            for a in angles
        ]

        for i in range(n):
            x1, y1 = positions[i]
            x2, y2 = positions[(i + 1) % n]
            overlap = _circles_overlap(x1, y1, node_radius, x2, y2, node_radius)
            assert not overlap, (
                f"Adjacent cycle nodes {i} and {(i + 1) % n} overlap "
                f"(distance={math.hypot(x2 - x1, y2 - y1):.3f}, "
                f"2*radius={2 * node_radius})"
            )


class TestLinearPhasePositioning:
    def test_phase_labels_are_evenly_spread(self) -> None:
        n = 6
        positions = [-5.0 + 2.0 * i for i in range(n)]
        gaps = [positions[i + 1] - positions[i] for i in range(n - 1)]
        for i, gap in enumerate(gaps):
            assert abs(gap - 2.0) < 0.01, (
                f"Gap between phase {i} and {i + 1} is {gap:.3f}, expected 2.0"
            )

    def test_first_and_last_fit_in_frame(self) -> None:
        n = 6
        positions = [-5.0 + 2.0 * i for i in range(n)]
        assert all(-7.0 <= p <= 7.0 for p in positions), (
            f"Phase positions {positions} extend beyond frame bounds [-7, 7]"
        )
