import re
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import yaml
from diagrams_generation.domain import (
    DiagramCluster,
    DiagramConnection,
    DiagramDefinition,
    DiagramNode,
)

_SLUG_PATTERN = re.compile(r"[a-z0-9_-]+")


def load_from_yaml_string(
    yaml_string: str, source: str = "<yaml string>"
) -> DiagramDefinition:
    data = cast(object, yaml.safe_load(yaml_string))
    document = _require_mapping(data, "document", source)

    name = _required_string(document, "name", "document", source)
    filename = _required_string(document, "filename", "document", source)
    _require_slug(filename, "filename", source)
    direction = _optional_string(document, "direction", "document", source)

    return DiagramDefinition(
        name=name,
        filename=filename,
        direction="LR" if direction is None else direction,
        nodes=_parse_nodes(document.get("nodes", []), "nodes", source),
        clusters=_parse_clusters(
            document.get("clusters", []), "clusters", source
        ),
        connections=_parse_connections(
            document.get("connections", []), "connections", source
        ),
        graph_attr=_parse_attr_map(
            document.get("graph_attr"), "graph_attr", source
        ),
        node_attr=_parse_attr_map(
            document.get("node_attr"), "node_attr", source
        ),
    )


def load_from_file(file_path: Path) -> DiagramDefinition:
    content = file_path.read_text(encoding="utf-8")
    return load_from_yaml_string(content, str(file_path))


def _parse_nodes(
    raw_nodes: object, context: str, source: str
) -> tuple[DiagramNode, ...]:
    nodes = _require_list(raw_nodes, context, source)
    return tuple(
        _parse_node(node, f"{context}[{index}]", source)
        for index, node in enumerate(nodes)
    )


def _parse_node(node: object, context: str, source: str) -> DiagramNode:
    node_map = _require_mapping(node, context, source)
    return DiagramNode(
        identifier=_required_string(node_map, "id", context, source),
        label=_required_string(node_map, "label", context, source),
        node_type=_required_string(node_map, "type", context, source),
    )


def _parse_clusters(
    raw_clusters: object, context: str, source: str
) -> tuple[DiagramCluster, ...]:
    clusters = _require_list(raw_clusters, context, source)
    return tuple(
        _parse_cluster(cluster, f"{context}[{index}]", source)
        for index, cluster in enumerate(clusters)
    )


def _parse_cluster(
    cluster: object, context: str, source: str
) -> DiagramCluster:
    cluster_map = _require_mapping(cluster, context, source)
    return DiagramCluster(
        name=_required_string(cluster_map, "name", context, source),
        nodes=_parse_nodes(
            cluster_map.get("nodes", []), f"{context}.nodes", source
        ),
    )


def _parse_connections(
    raw_connections: object, context: str, source: str
) -> tuple[DiagramConnection, ...]:
    connections = _require_list(raw_connections, context, source)
    return tuple(
        _parse_connection(connection, f"{context}[{index}]", source)
        for index, connection in enumerate(connections)
    )


def _parse_connection(
    connection: object, context: str, source: str
) -> DiagramConnection:
    connection_map = _require_mapping(connection, context, source)
    return DiagramConnection(
        from_node=_required_string(connection_map, "from", context, source),
        to_node=_required_string(connection_map, "to", context, source),
        label=_optional_string(connection_map, "label", context, source),
    )


def _parse_attr_map(raw: object, context: str, source: str) -> dict[str, str]:
    """Return a str→str dict from an optional YAML attribute mapping.

    Example YAML: graph_attr: {pad: "0.4", ranksep: "0.7"}
    Returns {} when raw is None (key absent) so the diagram uses defaults.
    """
    if raw is None:
        return {}
    mapping = _require_mapping(raw, context, source)
    return {
        _require_string_key(key, context, source): _require_string_value(
            value, f"{context}.{key}", source
        )
        for key, value in mapping.items()
    }


def _require_mapping(
    value: object, context: str, source: str
) -> dict[object, object]:
    if isinstance(value, dict):
        return cast(dict[object, object], value)
    raise ValueError(
        f"Invalid YAML in {source}: expected mapping at {context}, "
        f"got {type(value).__name__}"
    )


def _require_list(value: object, context: str, source: str) -> list[object]:
    if isinstance(value, list):
        return cast(list[object], value)
    raise ValueError(
        f"Invalid YAML in {source}: expected list at {context}, "
        f"got {type(value).__name__}"
    )


def _required_string(
    mapping: Mapping[object, object], key: str, context: str, source: str
) -> str:
    return _require_string_value(mapping.get(key), f"{context}.{key}", source)


def _optional_string(
    mapping: Mapping[object, object], key: str, context: str, source: str
) -> str | None:
    value = mapping.get(key)
    if value is None:
        return None
    return _require_string_value(value, f"{context}.{key}", source)


def _require_string_value(value: object, context: str, source: str) -> str:
    if isinstance(value, str):
        return value
    raise ValueError(
        f"Invalid YAML in {source}: expected string at {context}, "
        f"got {value!r} ({type(value).__name__})"
    )


def _require_string_key(key: object, context: str, source: str) -> str:
    if isinstance(key, str):
        return key
    raise ValueError(
        f"Invalid YAML in {source}: expected string key at {context}, "
        f"got {key!r} ({type(key).__name__})"
    )


def _require_slug(value: str, field: str, source: str) -> None:
    if _SLUG_PATTERN.fullmatch(value):
        return
    raise ValueError(
        f"Invalid {field} {value!r} in {source}: "
        f"expected slug matching {_SLUG_PATTERN.pattern}"
    )
