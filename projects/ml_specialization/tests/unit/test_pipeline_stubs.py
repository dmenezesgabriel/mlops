from pathlib import Path
from types import ModuleType

import pytest
from ml_specialization.pipelines import (
    collect,
    deploy,
    evaluate,
    features,
    monitor,
    preprocess,
    train,
    tune,
)


@pytest.mark.parametrize(
    ("module", "command"),
    [
        pytest.param(collect, "collect", id="collect"),
        pytest.param(preprocess, "preprocess", id="preprocess"),
        pytest.param(features, "features", id="features"),
        pytest.param(train, "train", id="train"),
        pytest.param(tune, "tune", id="tune"),
        pytest.param(evaluate, "evaluate", id="evaluate"),
        pytest.param(deploy, "deploy", id="deploy"),
        pytest.param(monitor, "monitor", id="monitor"),
    ],
)
def test_pipeline_run_raises_not_implemented(
    module: ModuleType,
    command: str,
    tmp_path: Path,
    project_config_yaml: str,
) -> None:
    # Arrange
    config_path = tmp_path / "configs" / "project.yaml"
    config_path.parent.mkdir()
    config_path.write_text(project_config_yaml, encoding="utf-8")

    # Act / Assert
    with pytest.raises(NotImplementedError, match=command):
        module.run(config_path)
