from dataclasses import dataclass


@dataclass(frozen=True)
class DiagramNode:
    identifier: str
    label: str
    node_type: str


@dataclass(frozen=True)
class DiagramCluster:
    name: str
    nodes: tuple[DiagramNode, ...]


@dataclass(frozen=True)
class DiagramConnection:
    from_node: str
    to_node: str
    label: str | None = None


class DiagramDefinition:
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
        # Graphviz graph-level attributes (pad, ranksep, dpi, …).
        # Defaults to empty so callers that omit it get standard layout.
        self.graph_attr: dict[str, str] = graph_attr or {}
        # Graphviz node-level attributes (fontsize, shape, …).
        self.node_attr: dict[str, str] = node_attr or {}
        self._validate()

    def _validate(self) -> None:
        valid_directions = {"TB", "BT", "LR", "RL"}
        if self.direction not in valid_directions:
            raise ValueError(
                f"Invalid direction {self.direction!r}, expected one of {valid_directions}"
            )

        all_identifiers = {node.identifier for node in self.nodes}
        for cluster in self.clusters:
            all_identifiers.update(node.identifier for node in cluster.nodes)

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
