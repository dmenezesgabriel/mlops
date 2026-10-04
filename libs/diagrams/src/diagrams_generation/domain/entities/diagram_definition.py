from collections.abc import Iterable

from diagrams_generation.domain.value_objects.diagram_cluster import (
    DiagramCluster,
)
from diagrams_generation.domain.value_objects.diagram_connection import (
    DiagramConnection,
)
from diagrams_generation.domain.value_objects.diagram_node import DiagramNode


def _first_duplicate(values: Iterable[str]) -> str | None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            return value
        seen.add(value)

    return None


class DiagramDefinition:
    """Domain Entity representing a structured architecture diagram."""

    def __init__(
        self,
        name: str,
        filename: str,
        direction: str,
        nodes: tuple[DiagramNode, ...],
        clusters: tuple[DiagramCluster, ...],
        connections: tuple[DiagramConnection, ...],
        graph_attr: dict[str, str] | None = None,
        node_attr: dict[str, str] | None = None,
    ) -> None:
        self.name = name
        self.filename = filename
        self.direction = direction
        self.nodes = nodes
        self.clusters = clusters
        self.connections = connections
        self.graph_attr: dict[str, str] = graph_attr or {}
        self.node_attr: dict[str, str] = node_attr or {}
        self._validate()

    def _validate(self) -> None:
        valid_directions = {"TB", "BT", "LR", "RL"}
        if self.direction not in valid_directions:
            raise ValueError(
                f"Invalid direction {self.direction!r}, expected one of {valid_directions}"
            )

        identifiers = [node.identifier for node in self.nodes]
        for cluster in self.clusters:
            identifiers.extend(node.identifier for node in cluster.nodes)

        duplicate = _first_duplicate(identifiers)
        if duplicate is not None:
            raise ValueError(
                f"Duplicate node identifier {duplicate!r}: "
                f"expected unique identifiers across nodes and clusters"
            )

        self._validate_connections(set(identifiers))

    def _validate_connections(self, all_identifiers: set[str]) -> None:
        for connection in self.connections:
            if connection.from_node not in all_identifiers:
                raise ValueError(
                    f"Offending connection: from_node {connection.from_node!r} "
                    f"not found in defined node identifiers {all_identifiers}"
                )
            if connection.to_node not in all_identifiers:
                raise ValueError(
                    f"Offending connection: to_node {connection.to_node!r} "
                    f"not found in defined node identifiers {all_identifiers}"
                )
