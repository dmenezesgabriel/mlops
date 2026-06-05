from __future__ import annotations

from pydantic import field_validator, model_validator
from pydantic.dataclasses import dataclass

from videos.core.domain._base import PydanticModel


@dataclass(frozen=True)
class TimelineEvent(PydanticModel):
    time_seconds: float
    action: str
    target_object_id: str

    @field_validator("time_seconds")
    @classmethod
    def _time_must_be_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError(
                f"TimelineEvent time_seconds must be >= 0, got {v}"
            )
        return v

    @field_validator("target_object_id")
    @classmethod
    def _target_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(
                f"TimelineEvent target_object_id must not be empty, got {v!r}"
            )
        return v


@dataclass(frozen=True)
class TimelineSpec(PydanticModel):
    events: tuple[TimelineEvent, ...] = ()

    @model_validator(mode="after")
    def _events_must_be_increasing(self) -> "TimelineSpec":
        if not self.events:
            return self
        times = [e.time_seconds for e in self.events]
        for i in range(1, len(times)):
            if times[i] <= times[i - 1]:
                raise ValueError(
                    f"TimelineSpec events must have strictly increasing time_seconds, "
                    f"found {times[i - 1]} followed by {times[i]}"
                )
        return self
