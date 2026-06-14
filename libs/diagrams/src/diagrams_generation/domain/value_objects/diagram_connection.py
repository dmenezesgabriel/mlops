from dataclasses import dataclass


@dataclass(frozen=True)
class DiagramConnection:
    from_node: str
    to_node: str
    label: str | None = None
