from __future__ import annotations

from mlops_videos.concepts.bias_variance_tradeoff import BiasVarianceExtension
from mlops_videos.concepts.crisp_dm import CrispDmExtension
from mlops_videos.concepts.mlops_lifecycle import MlopsLifecycleExtension
from mlops_videos.concepts.underfit_vs_overfit import UnderfitOverfitExtension
from mlops_videos.core._domain._narrative import Narrative


def _extensions() -> list[tuple[str, Narrative]]:
    exts = (
        BiasVarianceExtension(),
        CrispDmExtension(),
        MlopsLifecycleExtension(),
        UnderfitOverfitExtension(),
    )
    return [(e.concept.id.value, e.create_narrative()) for e in exts]


class TestNarrativeDuration:
    def test_all_narratives_within_40_to_75_seconds(self) -> None:
        for name, narrative in _extensions():
            d = narrative.total_duration
            assert 40.0 <= d <= 75.0, (
                f"{name}: total_duration={d:.1f}s, expected [40, 75]"
            )


class TestVisualKeyUniqueness:
    def test_no_duplicate_kind_visual_key_combinations(self) -> None:
        for name, narrative in _extensions():
            seen: set[tuple[str, str]] = set()
            for beat in narrative.beats:
                key = (beat.kind.value, beat.visual_key)
                assert key not in seen, (
                    f"{name}: duplicate beat ({beat.kind.value}, {beat.visual_key})"
                )
                seen.add(key)


class TestBeatSequence:
    def test_all_beats_have_positive_duration(self) -> None:
        for name, narrative in _extensions():
            for beat in narrative.beats:
                assert beat.narration.duration_seconds > 0, (
                    f"{name}: beat {beat.visual_key} has zero duration"
                )
