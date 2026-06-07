from __future__ import annotations

from typing import Protocol


class Telemetry(Protocol):
    def record_event(
        self, event_name: str, attributes: dict[str, object]
    ) -> None: ...

    def record_error(
        self, error: Exception, attributes: dict[str, object]
    ) -> None: ...
