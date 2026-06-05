from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VisualComponent:
    component_id: str
    description: str
