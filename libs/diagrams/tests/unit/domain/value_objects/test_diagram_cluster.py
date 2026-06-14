from diagrams_generation.domain.value_objects.diagram_cluster import (
    DiagramCluster,
)
from diagrams_generation.domain.value_objects.diagram_node import DiagramNode


class TestDiagramCluster:
    def test_should_initialize_valid_cluster(self) -> None:
        # Arrange
        node = DiagramNode(
            identifier="web",
            label="Web Server",
            node_type="onprem.compute.Server",
        )
        nodes = (node,)
        name = "frontend"

        # Act
        cluster = DiagramCluster(name=name, nodes=nodes)

        # Assert
        assert cluster.name == name
        assert cluster.nodes == nodes
