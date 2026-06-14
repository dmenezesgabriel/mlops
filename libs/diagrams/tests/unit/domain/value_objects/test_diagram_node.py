from diagrams_generation.domain.value_objects.diagram_node import DiagramNode


class TestDiagramNode:
    def test_should_initialize_valid_node(self) -> None:
        # Arrange
        identifier = "db"
        label = "Database"
        node_type = "onprem.database.PostgreSQL"

        # Act
        node = DiagramNode(
            identifier=identifier, label=label, node_type=node_type
        )

        # Assert
        assert node.identifier == identifier
        assert node.label == label
        assert node.node_type == node_type
