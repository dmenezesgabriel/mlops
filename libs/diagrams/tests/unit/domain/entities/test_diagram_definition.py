import pytest
from diagrams_generation.domain.entities.diagram_definition import (
    DiagramDefinition,
)
from diagrams_generation.domain.value_objects.diagram_connection import (
    DiagramConnection,
)
from diagrams_generation.domain.value_objects.diagram_node import DiagramNode


class TestDiagramDefinition:
    def test_should_raise_value_error_when_connection_references_missing_node(
        self,
    ) -> None:
        # Arrange
        nodes = (
            DiagramNode(
                identifier="a", label="A", node_type="onprem.compute.Server"
            ),
        )
        connections = (DiagramConnection(from_node="a", to_node="b"),)

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            DiagramDefinition(
                name="Test",
                filename="test",
                direction="LR",
                nodes=nodes,
                clusters=(),
                connections=connections,
            )
        assert "b" in str(exc_info.value)
        assert "a" in str(exc_info.value)

    def test_should_raise_value_error_with_invalid_direction(self) -> None:
        # Arrange
        nodes = (
            DiagramNode(
                identifier="a", label="A", node_type="onprem.compute.Server"
            ),
        )

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            DiagramDefinition(
                name="Test",
                filename="test",
                direction="INVALID",
                nodes=nodes,
                clusters=(),
                connections=(),
            )
        assert "INVALID" in str(exc_info.value)
