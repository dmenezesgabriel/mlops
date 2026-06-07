import pytest
from videos.core.domain.timeline import TimelineEvent, TimelineSpec


class TestTimelineEvent:
    def test_rejects_negative_time(self) -> None:
        with pytest.raises(ValueError, match="time_seconds"):
            TimelineEvent(
                time_seconds=-1, action="appear", target_object_id="o1"
            )

    def test_rejects_empty_target(self) -> None:
        with pytest.raises(ValueError, match="target_object_id"):
            TimelineEvent(
                time_seconds=0.0, action="appear", target_object_id=""
            )

    def test_accepts_valid_event(self) -> None:
        ev = TimelineEvent(
            time_seconds=1.0, action="fade_in", target_object_id="title_1"
        )
        assert ev.time_seconds == 1.0
        assert ev.action == "fade_in"
        assert ev.target_object_id == "title_1"


class TestTimelineSpec:
    def test_accepts_empty_events(self) -> None:
        spec = TimelineSpec()
        assert spec.events == ()

    def test_accepts_single_event(self) -> None:
        spec = TimelineSpec(
            events=(
                TimelineEvent(
                    time_seconds=0.0, action="appear", target_object_id="o1"
                ),
            )
        )
        assert len(spec.events) == 1

    def test_rejects_non_increasing_times(self) -> None:
        with pytest.raises(ValueError, match="increasing time_seconds"):
            TimelineSpec(
                events=(
                    TimelineEvent(
                        time_seconds=2.0,
                        action="appear",
                        target_object_id="o1",
                    ),
                    TimelineEvent(
                        time_seconds=1.0,
                        action="appear",
                        target_object_id="o2",
                    ),
                )
            )

    def test_rejects_equal_times(self) -> None:
        with pytest.raises(ValueError, match="increasing time_seconds"):
            TimelineSpec(
                events=(
                    TimelineEvent(
                        time_seconds=1.0,
                        action="appear",
                        target_object_id="o1",
                    ),
                    TimelineEvent(
                        time_seconds=1.0,
                        action="appear",
                        target_object_id="o2",
                    ),
                )
            )

    def test_accepts_increasing_times(self) -> None:
        spec = TimelineSpec(
            events=(
                TimelineEvent(
                    time_seconds=0.0, action="appear", target_object_id="o1"
                ),
                TimelineEvent(
                    time_seconds=1.0, action="fade_in", target_object_id="o2"
                ),
                TimelineEvent(
                    time_seconds=3.0, action="fade_out", target_object_id="o1"
                ),
            )
        )
        assert len(spec.events) == 3
