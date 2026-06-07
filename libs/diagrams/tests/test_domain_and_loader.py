import pytest
from diagrams_generation.core.loader import load_from_yaml_string
from diagrams_generation.domain.diagram import (
    DiagramConnection,
    DiagramDefinition,
    DiagramNode,
)


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


class TestLoader:
    def test_should_load_valid_yaml(self) -> None:
        # Arrange
        yaml_content = """
name: "MLOps Lifecycle"
filename: "mlops_lifecycle"
direction: "LR"
nodes:
  - id: raw_data
    label: "Raw Data"
    type: "onprem.storage.S3"
connections:
  - from: raw_data
    to: raw_data
"""

        # Act
        definition = load_from_yaml_string(yaml_content)

        # Assert
        assert definition.name == "MLOps Lifecycle"
        assert definition.filename == "mlops_lifecycle"
        assert len(definition.nodes) == 1
        assert definition.nodes[0].identifier == "raw_data"
