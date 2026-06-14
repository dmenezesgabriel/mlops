from dataclasses import dataclass


@dataclass(frozen=True)
class DiagramNode:
    identifier: str
    label: str
    node_type: str
