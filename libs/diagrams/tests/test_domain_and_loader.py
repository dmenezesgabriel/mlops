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

    def test_should_load_graph_attr_when_present(self) -> None:
        # Exercises the graph_attr YAML key → DiagramDefinition.graph_attr path.
        # Example: load_from_yaml_string('...\ngraph_attr:\n  pad: "0.4"\n')
        yaml_content = """
name: "Test"
filename: "test"
direction: "TB"
graph_attr:
  pad: "0.4"
  ranksep: "0.7"
nodes:
  - id: n1
    label: "Node 1"
    type: "programming.flowchart.Action"
"""

        definition = load_from_yaml_string(yaml_content)

        assert definition.graph_attr == {"pad": "0.4", "ranksep": "0.7"}

    def test_should_default_graph_attr_to_empty_dict_when_absent(self) -> None:
        # graph_attr is optional; omitting it must not raise and must be {}.
        yaml_content = """
name: "Test"
filename: "test"
direction: "LR"
nodes:
  - id: n1
    label: "Node 1"
    type: "programming.flowchart.Action"
"""

        definition = load_from_yaml_string(yaml_content)

        assert definition.graph_attr == {}

    def test_should_load_node_attr_when_present(self) -> None:
        # Exercises the node_attr YAML key → DiagramDefinition.node_attr path.
        yaml_content = """
name: "Test"
filename: "test"
direction: "LR"
node_attr:
  fontsize: "14"
nodes:
  - id: n1
    label: "Node 1"
    type: "programming.flowchart.Action"
"""

        definition = load_from_yaml_string(yaml_content)

        assert definition.node_attr == {"fontsize": "14"}

    def test_should_default_node_attr_to_empty_dict_when_absent(self) -> None:
        # node_attr is optional; omitting it must not raise and must be {}.
        yaml_content = """
name: "Test"
filename: "test"
direction: "LR"
nodes:
  - id: n1
    label: "Node 1"
    type: "programming.flowchart.Action"
"""

        definition = load_from_yaml_string(yaml_content)

        assert definition.node_attr == {}
