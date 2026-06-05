from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TimelineEvent:
    time_seconds: float
    action: str
    target_object_id: str

    def __post_init__(self) -> None:
        if self.time_seconds < 0:
            raise ValueError(f"TimelineEvent time_seconds must be >= 0, got {self.time_seconds}")
        if not self.target_object_id.strip():
            raise ValueError(
                f"TimelineEvent target_object_id must not be empty, got {self.target_object_id!r}"
            )


@dataclass(frozen=True)
class TimelineSpec:
    events: tuple[TimelineEvent, ...] = ()

    def __post_init__(self) -> None:
        if not self.events:
            return
        times = [e.time_seconds for e in self.events]
        for i in range(1, len(times)):
            if times[i] <= times[i - 1]:
                raise ValueError(
                    f"TimelineSpec events must have strictly increasing time_seconds, "
                    f"found {times[i - 1]} followed by {times[i]}"
                )
