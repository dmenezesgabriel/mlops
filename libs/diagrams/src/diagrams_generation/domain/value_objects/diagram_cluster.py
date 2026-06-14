from dataclasses import dataclass

from diagrams_generation.domain.value_objects.diagram_node import DiagramNode


@dataclass(frozen=True)
class DiagramCluster:
    name: str
    nodes: tuple[DiagramNode, ...]
