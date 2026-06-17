import pytest
from pydantic import ValidationError
from videos.domain.value_objects.timeline import TimelineEvent, TimelineSpec


class TestTimelineEvent:
    def test_valid_event(self) -> None:
        event = TimelineEvent(
            time_seconds=1.0, action="appear", target_object_id="obj1"
        )
        assert event.time_seconds == 1.0

    def test_negative_time_raises(self) -> None:
        with pytest.raises(ValidationError):
            TimelineEvent(
                time_seconds=-1.0, action="appear", target_object_id="obj1"
            )

    def test_empty_target_raises(self) -> None:
        with pytest.raises(ValidationError):
            TimelineEvent(
                time_seconds=0.0, action="appear", target_object_id=""
            )


class TestTimelineSpec:
    def test_empty_events_allowed(self) -> None:
        spec = TimelineSpec(events=())
        assert spec.events == ()

    def test_non_increasing_times_raises(self) -> None:
        with pytest.raises(ValidationError):
            TimelineSpec(
                events=(
                    TimelineEvent(
                        time_seconds=1.0,
                        action="appear",
                        target_object_id="a",
                    ),
                    TimelineEvent(
                        time_seconds=0.5,
                        action="appear",
                        target_object_id="b",
                    ),
                )
            )
