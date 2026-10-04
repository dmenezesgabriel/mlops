import pytest
from diagrams_generation.domain.entities.diagram_definition import (
    DiagramDefinition,
)
from diagrams_generation.domain.value_objects.diagram_cluster import (
    DiagramCluster,
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

    def test_should_raise_value_error_when_node_identifier_duplicated(
        self,
    ) -> None:
        # Arrange
        nodes = (
            DiagramNode(
                identifier="a", label="A", node_type="onprem.compute.Server"
            ),
            DiagramNode(
                identifier="a", label="A2", node_type="onprem.compute.Server"
            ),
        )

        # Act & Assert
        with pytest.raises(ValueError, match="'a'"):
            DiagramDefinition(
                name="Test",
                filename="test",
                direction="LR",
                nodes=nodes,
                clusters=(),
                connections=(),
            )

    def test_should_raise_value_error_when_from_node_missing(self) -> None:
        # Arrange
        nodes = (
            DiagramNode(
                identifier="a", label="A", node_type="onprem.compute.Server"
            ),
        )
        connections = (DiagramConnection(from_node="x", to_node="a"),)

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
        assert "x" in str(exc_info.value)
        assert "a" in str(exc_info.value)

    def test_should_raise_value_error_when_cluster_node_identifier_duplicated(
        self,
    ) -> None:
        # Arrange
        nodes = (
            DiagramNode(
                identifier="a", label="A", node_type="onprem.compute.Server"
            ),
        )
        clusters = (
            DiagramCluster(
                name="cluster",
                nodes=(
                    DiagramNode(
                        identifier="a",
                        label="A2",
                        node_type="onprem.compute.Server",
                    ),
                ),
            ),
        )

        # Act & Assert
        with pytest.raises(ValueError, match="'a'"):
            DiagramDefinition(
                name="Test",
                filename="test",
                direction="LR",
                nodes=nodes,
                clusters=clusters,
                connections=(),
            )
