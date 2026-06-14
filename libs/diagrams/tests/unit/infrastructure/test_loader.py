from diagrams_generation.infrastructure.loader import load_from_yaml_string


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
