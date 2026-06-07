import importlib
from pathlib import Path
from typing import Any

from diagrams_generation.domain.diagram import DiagramDefinition


class MingrammerDiagramRenderer:
    def _check_dependencies(self) -> tuple[Any, Any, Any]:
        try:
            diagram_module = importlib.import_module("diagrams")
        except ImportError as e:
            raise ImportError(
                "The 'diagrams' package is not installed. Please install it using: "
                "pip install diagrams-generation[diagrams]"
            ) from e
        diagram_class = diagram_module.Diagram
        cluster_class = diagram_module.Cluster
        edge_class = diagram_module.Edge
        return diagram_class, cluster_class, edge_class

    def _resolve_node_class(self, node_type: str) -> Any:
        parts = node_type.split(".")
        if len(parts) < 2:
            raise ValueError(
                f"Invalid node type {node_type!r}: expected format "
                f"'provider.category.ClassName' or 'custom.ClassName'"
            )
        class_name = parts[-1]
        module_path = "diagrams." + ".".join(parts[:-1])
        try:
            module = importlib.import_module(module_path)  # nosemgrep
        except ImportError as e:
            raise ValueError(
                f"Could not import module {module_path!r}: {e}"
            ) from e
        node_class = getattr(module, class_name, None)
        if node_class is None:
            raise ValueError(
                f"Class {class_name!r} not found in module {module_path!r}"
            )
        return node_class

    def _instantiate_nodes(
        self, definition: DiagramDefinition, instances: dict[str, Any]
    ) -> None:
        for node in definition.nodes:
            node_class = self._resolve_node_class(node.node_type)
            instances[node.identifier] = node_class(node.label)

    def _instantiate_clusters(
        self,
        definition: DiagramDefinition,
        instances: dict[str, Any],
        cluster_class: Any,
    ) -> None:
        for cluster in definition.clusters:
            with cluster_class(cluster.name):
                for node in cluster.nodes:
                    node_class = self._resolve_node_class(node.node_type)
                    instances[node.identifier] = node_class(node.label)

    def _draw_connections(
        self,
        definition: DiagramDefinition,
        instances: dict[str, Any],
        edge_class: Any,
    ) -> None:
        for connection in definition.connections:
            from_instance = instances[connection.from_node]
            to_instance = instances[connection.to_node]
            if connection.label:
                (
                    from_instance
                    >> edge_class(label=connection.label)
                    >> to_instance
                )
                continue
            from_instance >> to_instance

    def render(
        self, definition: DiagramDefinition, output_directory: str
    ) -> str:
        diagram_class, cluster_class, edge_class = self._check_dependencies()
        target_path = Path(output_directory) / definition.filename
        target_path.parent.mkdir(parents=True, exist_ok=True)

        with diagram_class(
            name=definition.name,
            filename=str(target_path),
            direction=definition.direction,
            show=False,
            outformat="png",
        ):
            instances: dict[str, Any] = {}
            self._instantiate_nodes(definition, instances)
            self._instantiate_clusters(definition, instances, cluster_class)
            self._draw_connections(definition, instances, edge_class)

        return f"{target_path}.png"
