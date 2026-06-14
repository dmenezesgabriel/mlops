from diagrams_generation.domain.value_objects.diagram_connection import (
    DiagramConnection,
)


class TestDiagramConnection:
    def test_should_initialize_valid_connection_without_label(self) -> None:
        # Arrange
        from_node = "web"
        to_node = "db"

        # Act
        conn = DiagramConnection(from_node=from_node, to_node=to_node)

        # Assert
        assert conn.from_node == from_node
        assert conn.to_node == to_node
        assert conn.label is None

    def test_should_initialize_valid_connection_with_label(self) -> None:
        # Arrange
        from_node = "web"
        to_node = "db"
        label = "queries"

        # Act
        conn = DiagramConnection(
            from_node=from_node, to_node=to_node, label=label
        )

        # Assert
        assert conn.from_node == from_node
        assert conn.to_node == to_node
        assert conn.label == label
