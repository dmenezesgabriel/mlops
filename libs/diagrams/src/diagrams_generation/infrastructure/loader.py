from pathlib import Path
from typing import Any

import yaml
from diagrams_generation.domain.diagram import (
    DiagramCluster,
    DiagramConnection,
    DiagramDefinition,
    DiagramNode,
)


def load_from_yaml_string(yaml_string: str) -> DiagramDefinition:
    data = yaml.safe_load(yaml_string)
    if not isinstance(data, dict):
        raise ValueError(
            f"Invalid YAML structure: expected a mapping, got {type(data).__name__}"
        )

    nodes = _parse_nodes(data.get("nodes", []))
    clusters = _parse_clusters(data.get("clusters", []))
    connections = _parse_connections(data.get("connections", []))
    graph_attr = _parse_graph_attr(data.get("graph_attr"))
    node_attr = _parse_graph_attr(data.get("node_attr"))

    return DiagramDefinition(
        name=str(data["name"]),
        filename=str(data["filename"]),
        direction=str(data.get("direction", "LR")),
        nodes=nodes,
        clusters=clusters,
        connections=connections,
        graph_attr=graph_attr,
        node_attr=node_attr,
    )


def load_from_file(file_path: Path) -> DiagramDefinition:
    content = file_path.read_text(encoding="utf-8")
    return load_from_yaml_string(content)


def _parse_nodes(raw_nodes: list[Any]) -> tuple[DiagramNode, ...]:
    return tuple(
        DiagramNode(
            identifier=str(node["id"]),
            label=str(node["label"]),
            node_type=str(node["type"]),
        )
        for node in raw_nodes
    )


def _parse_clusters(raw_clusters: list[Any]) -> tuple[DiagramCluster, ...]:
    return tuple(
        DiagramCluster(
            name=str(cluster["name"]),
            nodes=_parse_nodes(cluster.get("nodes", [])),
        )
        for cluster in raw_clusters
    )


def _parse_connections(
    raw_connections: list[Any],
) -> tuple[DiagramConnection, ...]:
    return tuple(
        DiagramConnection(
            from_node=str(connection["from"]),
            to_node=str(connection["to"]),
            label=connection.get("label"),
        )
        for connection in raw_connections
    )


def _parse_graph_attr(raw: Any) -> dict[str, str]:
    """Return a str→str dict from the optional YAML graph_attr mapping.

    Example YAML: graph_attr: {pad: "0.4", ranksep: "0.7"}
    Returns {} when raw is None (key absent) so the diagram uses defaults.
    """
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(
            f"Invalid graph_attr {raw!r}: expected a string-keyed mapping, "
            f"got {type(raw).__name__}"
        )
    return {str(k): str(v) for k, v in raw.items()}
