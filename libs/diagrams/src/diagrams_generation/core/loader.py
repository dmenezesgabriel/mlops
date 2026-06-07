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

    return DiagramDefinition(
        name=str(data["name"]),
        filename=str(data["filename"]),
        direction=str(data.get("direction", "LR")),
        nodes=nodes,
        clusters=clusters,
        connections=connections,
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
