from pathlib import Path

import pytest
from diagrams_generation.infrastructure.loader import (
    load_from_file,
    load_from_yaml_string,
)


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


_VALID_NODE = '  - id: a\n    label: "L"\n    type: "a.B"\n'
_HEADER = 'name: "n"\nfilename: "f"\n'


class TestLoaderValidation:
    @pytest.mark.parametrize(
        ("yaml_content", "expected_fragment"),
        [
            pytest.param(
                'filename: "f"\n', "document.name", id="missing-name"
            ),
            pytest.param(
                'name: "n"\n', "document.filename", id="missing-filename"
            ),
            pytest.param(
                _HEADER + 'nodes:\n  - label: "L"\n    type: "a.B"\n',
                "nodes[0].id",
                id="missing-node-id",
            ),
            pytest.param(
                _HEADER + 'nodes:\n  - id: a\n    type: "a.B"\n',
                "nodes[0].label",
                id="missing-node-label",
            ),
            pytest.param(
                _HEADER + 'nodes:\n  - id: a\n    label: "L"\n',
                "nodes[0].type",
                id="missing-node-type",
            ),
            pytest.param(
                _HEADER + "clusters:\n  - nodes: []\n",
                "clusters[0].name",
                id="missing-cluster-name",
            ),
            pytest.param(
                _HEADER
                + "nodes:\n"
                + _VALID_NODE
                + "connections:\n  - to: a\n",
                "connections[0].from",
                id="missing-connection-from",
            ),
            pytest.param(
                _HEADER
                + "nodes:\n"
                + _VALID_NODE
                + "connections:\n  - from: a\n",
                "connections[0].to",
                id="missing-connection-to",
            ),
        ],
    )
    def test_should_raise_value_error_naming_key_when_required_key_missing(
        self, yaml_content: str, expected_fragment: str
    ) -> None:
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            load_from_yaml_string(yaml_content)

        assert expected_fragment in str(exc_info.value)

    @pytest.mark.parametrize(
        ("yaml_content", "expected_fragment"),
        [
            pytest.param(_HEADER + "nodes: 42\n", "nodes", id="nodes-int"),
            pytest.param(_HEADER + 'nodes: "abc"\n', "nodes", id="nodes-str"),
            pytest.param(
                _HEADER + "clusters: 42\n", "clusters", id="clusters-int"
            ),
            pytest.param(
                _HEADER + "connections: 42\n",
                "connections",
                id="connections-int",
            ),
            pytest.param(
                _HEADER + "nodes:\n  - 42\n", "nodes[0]", id="node-entry-int"
            ),
            pytest.param(
                _HEADER + "graph_attr: 42\n", "graph_attr", id="graph-attr-int"
            ),
            pytest.param(
                _HEADER + "node_attr:\n  - 1\n",
                "node_attr",
                id="node-attr-list",
            ),
        ],
    )
    def test_should_raise_value_error_naming_context_when_section_shape_wrong(
        self, yaml_content: str, expected_fragment: str
    ) -> None:
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            load_from_yaml_string(yaml_content)

        assert expected_fragment in str(exc_info.value)
        assert "expected" in str(exc_info.value)

    @pytest.mark.parametrize(
        ("yaml_content", "expected_fragment"),
        [
            pytest.param(
                'name: 42\nfilename: "f"\n', "document.name", id="name-int"
            ),
            pytest.param(
                _HEADER + "direction: 42\n",
                "document.direction",
                id="direction-int",
            ),
            pytest.param(
                _HEADER
                + 'nodes:\n  - id: 1\n    label: "L"\n    type: "a.B"\n',
                "nodes[0].id",
                id="node-id-int",
            ),
            pytest.param(
                _HEADER + 'nodes:\n  - id: a\n    label: 0\n    type: "a.B"\n',
                "nodes[0].label",
                id="node-label-int",
            ),
            pytest.param(
                _HEADER
                + "nodes:\n"
                + _VALID_NODE
                + "connections:\n  - from: 1\n    to: a\n",
                "connections[0].from",
                id="connection-from-int",
            ),
            pytest.param(
                _HEADER + "graph_attr:\n  1: x\n",
                "graph_attr",
                id="graph-attr-int-key",
            ),
            pytest.param(
                _HEADER + 'graph_attr:\n  1: x\n  "1": y\n',
                "graph_attr",
                id="graph-attr-mixed-keys",
            ),
            pytest.param(
                _HEADER + "graph_attr:\n  on: x\n",
                "graph_attr",
                id="graph-attr-bool-key",
            ),
            pytest.param(
                _HEADER + "graph_attr:\n  pad: 0.4\n",
                "graph_attr.pad",
                id="graph-attr-float-value",
            ),
        ],
    )
    def test_should_raise_value_error_when_value_would_be_coerced(
        self, yaml_content: str, expected_fragment: str
    ) -> None:
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            load_from_yaml_string(yaml_content)

        assert expected_fragment in str(exc_info.value)

    @pytest.mark.parametrize(
        "filename",
        ["../escape", "/abs/override", "a b", "Name.Png", "sub/dir"],
    )
    def test_should_raise_value_error_when_filename_is_not_a_slug(
        self, filename: str
    ) -> None:
        # Arrange
        yaml_content = f'name: "n"\nfilename: "{filename}"\n'

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            load_from_yaml_string(yaml_content)

        assert filename in str(exc_info.value)

    def test_should_raise_value_error_when_connection_label_not_a_string(
        self,
    ) -> None:
        # Arrange
        yaml_content = (
            _HEADER
            + "nodes:\n"
            + _VALID_NODE
            + "connections:\n  - from: a\n    to: a\n    label: 42\n"
        )

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            load_from_yaml_string(yaml_content)

        assert "connections[0].label" in str(exc_info.value)

    def test_should_load_connection_label_when_string(self) -> None:
        # Arrange
        yaml_content = (
            _HEADER
            + "nodes:\n"
            + _VALID_NODE
            + "connections:\n  - from: a\n    to: a\n    label: retrain\n"
        )

        # Act
        definition = load_from_yaml_string(yaml_content)

        # Assert
        assert definition.connections[0].label == "retrain"

    def test_should_raise_value_error_naming_file_when_malformed(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        bad_file = tmp_path / "bad_definition.yaml"
        bad_file.write_text(_HEADER + "nodes: 42\n", encoding="utf-8")

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            load_from_file(bad_file)

        assert "bad_definition.yaml" in str(exc_info.value)
