import importlib.util
import os
import subprocess
import sys
import tomllib
from pathlib import Path
from types import ModuleType

import pytest
from cookiecutter.exceptions import (
    FailedHookException,
    OutputDirExistsException,
)
from data_science_scaffold.scaffold import TEMPLATE_DIR, generate

REPO_ROOT = Path(__file__).resolve().parents[4]
RUFF_CONFIG = REPO_ROOT / "pyproject.toml"


def test_generate_creates_mirror_project_tree(tmp_path: Path) -> None:
    # Act
    generated = generate("dummy_test_proj", tmp_path)

    # Assert
    assert generated == tmp_path / "dummy_test_proj"
    assert (generated / "configs" / "project.yaml").is_file()
    assert (generated / "feature_repo" / "feature_store.yaml").is_file()
    assert (generated / "docs" / "04_exploratory_data_analysis.md").is_file()
    assert (generated / "src" / "dummy_test_proj" / "py.typed").is_file()
    project_yaml = (generated / "configs" / "project.yaml").read_text(
        encoding="utf-8"
    )
    assert "tracking_uri: sqlite:///mlflow.db" in project_yaml


def test_generated_project_passes_ruff_gates(tmp_path: Path) -> None:
    # Arrange
    generated = generate("dummy_test_proj", tmp_path)
    _run_ruff("format", ".", cwd=generated)
    _run_ruff("check", "--fix", ".", cwd=generated)

    # Act
    format_result = _run_ruff("format", "--check", ".", cwd=generated)
    lint_result = _run_ruff("check", ".", cwd=generated)

    # Assert
    assert format_result.returncode == 0, format_result.stdout
    assert lint_result.returncode == 0, lint_result.stdout


def test_generated_project_gates_match_live_shape(tmp_path: Path) -> None:
    # Arrange
    generated = generate("dummy_test_proj", tmp_path)

    # Act
    makefile = (generated / "Makefile").read_text(encoding="utf-8")
    pyproject = tomllib.loads(
        (generated / "pyproject.toml").read_text(encoding="utf-8")
    )

    # Assert — rendered gates must match the live projects/* gate set
    assert '-e "*/node_modules/*"' in makefile
    assert '-x "*/node_modules/*"' not in makefile
    assert "--cov-fail-under" in makefile
    assert "bandit -q -r src -ll" in makefile
    assert "vulture --min-confidence 80 src" in makefile
    assert "xenon" in makefile
    assert "maintainability" in makefile
    assert pyproject["tool"]["pyright"]["typeCheckingMode"] == "strict"
    assert pyproject["tool"]["coverage"]["run"]["source"] == [
        "src",
        "tests",
    ]
    # `fakes` resolves under --import-mode=importlib only via this pin.
    assert pyproject["tool"]["pytest"]["ini_options"]["pythonpath"] == [
        "tests"
    ]
    # The stub bodies raise NotImplementedError; these args stay documented
    # but unused, and vulture would name them.
    assert pyproject["tool"]["vulture"]["ignore_names"] == [
        "raw_directory",
        "n_trials",
        "output_directory",
        "trips_path",
        "training_dataset_path",
    ]


def test_rendered_predict_normalizes_pyfunc_output(tmp_path: Path) -> None:
    # The scaffold env lacks feast/mlflow, so api.py can't be exec'd here;
    # pin the rendered normalization + ndarray fake shapes by source instead.
    generated = generate("dummy_test_proj", tmp_path)

    api_source = (
        generated / "src" / "dummy_test_proj" / "inference" / "api.py"
    ).read_text(encoding="utf-8")
    fakes_source = (generated / "tests" / "fakes.py").read_text(
        encoding="utf-8"
    )

    assert "np.asarray(raw_prediction).ravel()[0]" in api_source
    assert "cast(" not in api_source
    assert "np.array(self.predictions)" in fakes_source


def test_rendered_serving_resources_load_lazily(tmp_path: Path) -> None:
    # G-310: the rendered api.py must not eager-init at import — the config
    # load, FeatureStore, set_tracking_uri and load_model stay inside the
    # lazy builder (the live projects' shipped AF-105/AF-92 shape).
    generated = generate("dummy_test_proj", tmp_path)

    api_source = (
        generated / "src" / "dummy_test_proj" / "inference" / "api.py"
    ).read_text(encoding="utf-8")

    # The lazy seam exists and is cached behind a module-level sentinel.
    assert "@dataclass(frozen=True)" in api_source
    assert "def _load_serving_resources() -> _ServingResources:" in api_source
    assert "def _serving_resources() -> _ServingResources:" in api_source
    assert "_resources: _ServingResources | None = None" in api_source
    # Only a registry-level failure degrades to the 503 contract.
    assert "except MlflowException:" in api_source

    # No side-effecting call is unindented (module level); each lives inside
    # the lazy builder's body.
    assert "\nFeatureStore(repo_path=" not in api_source
    assert "\n    store = FeatureStore(repo_path=" in api_source
    assert "\nmlflow.set_tracking_uri(" not in api_source
    assert "\n    mlflow.set_tracking_uri(" in api_source
    assert (
        "model: PyFuncModel | None = mlflow.pyfunc.load_model(" in api_source
    )


def test_rendered_feature_contract_is_single_sourced(tmp_path: Path) -> None:
    # The scaffold env lacks feast/mlflow, so pin by source: the serving
    # surfaces must import the hourly_demand contract constants, not carry
    # private literal copies that can drift apart.
    generated = generate("dummy_test_proj", tmp_path)
    package = generated / "src" / "dummy_test_proj"
    api_source = (package / "inference" / "api.py").read_text(encoding="utf-8")
    batch_source = (package / "inference" / "batch_predict.py").read_text(
        encoding="utf-8"
    )
    contract_source = (package / "features" / "hourly_demand.py").read_text(
        encoding="utf-8"
    )

    assert "from dummy_test_proj.features.hourly_demand import" in api_source
    assert (
        "from dummy_test_proj.features.hourly_demand import FEATURE_COLUMNS"
        in batch_source
    )
    assert "_FEATURE_COLUMNS" not in api_source
    assert "_feature_columns" not in batch_source
    assert 'f"hourly_pickup_demand:' not in api_source
    assert "FEATURE_VIEW_NAME" in contract_source
    assert "def load_entity_df" in contract_source
    # The conformance pin ships inside the generated project's own suite.
    assert (
        generated / "tests" / "unit" / "features" / "test_hourly_demand.py"
    ).is_file()


def test_rendered_config_loader_rejects_non_string_section_keys(
    tmp_path: Path,
) -> None:
    # Arrange — G-16 probe: an int key under `paths:` must not coerce to "1"
    generated = generate("dummy_test_proj", tmp_path)
    module = _load_rendered_configuration(generated, "dummy_test_proj")
    config_path = generated / "configs" / "project.yaml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace(
            "paths:\n", "paths:\n  1: data/extra\n"
        ),
        encoding="utf-8",
    )

    # Act & Assert
    with pytest.raises(ValueError, match="expected string key"):
        module.ProjectConfigLoader().load(config_path)


def test_generated_configs_tree_has_no_include_stubs(tmp_path: Path) -> None:
    # The rendered configs/ dir must hold only project.yaml — the include:
    # convention was never implemented and the stubs errored on the wrong key.
    generated = generate("dummy_test_proj", tmp_path)

    assert sorted(
        entry.name for entry in (generated / "configs").iterdir()
    ) == ["project.yaml"]


@pytest.mark.parametrize(
    ("config_edit", "match"),
    [
        pytest.param(
            ("months: [1]", "months: [on, off]"),
            "expected integer list",
            id="bool_months",
        ),
        pytest.param(
            ("year: 2023", "year: yes"),
            "expected integer",
            id="bool_year",
        ),
        pytest.param(
            ("test_size: 0.2", "test_size: on"),
            "expected number",
            id="bool_test_size",
        ),
    ],
)
def test_rendered_config_loader_rejects_yaml_bool_values(
    tmp_path: Path, config_edit: tuple[str, str], match: str
) -> None:
    # Arrange — `isinstance(True, int)` is True; YAML-1.1 bools must not
    # pass the rendered numeric guards.
    generated = generate("dummy_test_proj", tmp_path)
    module = _load_rendered_configuration(generated, "dummy_test_proj")
    config_path = generated / "configs" / "project.yaml"
    old, new = config_edit
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace(old, new),
        encoding="utf-8",
    )

    # Act & Assert
    with pytest.raises(ValueError, match=match):
        module.ProjectConfigLoader().load(config_path)


def test_rendered_config_loader_rejects_config_outside_configs_dir(
    tmp_path: Path,
) -> None:
    # Arrange — `project_root` is derived as `config_path.parent.parent`;
    # a config outside `configs/` anchors every relative path to a
    # wrong root instead of failing.
    generated = generate("dummy_test_proj", tmp_path)
    module = _load_rendered_configuration(generated, "dummy_test_proj")
    config_path = generated / "project.yaml"
    config_path.write_text(
        (generated / "configs" / "project.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    # Act & Assert
    with pytest.raises(ValueError, match="configs/"):
        module.ProjectConfigLoader().load(config_path)


def test_rendered_config_loader_passes_through_memory_tracking_uri(
    tmp_path: Path,
) -> None:
    # Arrange — `sqlite:///:memory:` is an absolute form, not a relative
    # path to anchor under the project root.
    generated = generate("dummy_test_proj", tmp_path)
    module = _load_rendered_configuration(generated, "dummy_test_proj")
    config_path = generated / "configs" / "project.yaml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace(
            "sqlite:///mlflow.db", '"sqlite:///:memory:"'
        ),
        encoding="utf-8",
    )

    # Act
    config = module.ProjectConfigLoader().load(config_path)

    # Assert
    assert config.mlflow.tracking_uri == "sqlite:///:memory:"


@pytest.mark.parametrize("test_size", [0.0, 1.0, 1.5, -0.1])
def test_rendered_split_rejects_out_of_range_test_size(
    tmp_path: Path, test_size: float
) -> None:
    # Arrange — the pre-fix `max(1, int(n * (1 - test_size)))` silently
    # accepts the degenerate ratios the shipped projects reject.
    generated = generate("dummy_test_proj", tmp_path)
    module = _load_rendered_training(generated, "dummy_test_proj")
    dataset = module.pd.DataFrame({"pickup_count": range(10)})

    # Act & Assert
    with pytest.raises(ValueError, match=f"test_size {test_size}"):
        module.DemandDatasetSplitter().split(dataset, test_size)


@pytest.mark.parametrize("rows", [0, 1])
def test_rendered_split_rejects_unsplittable_dataset(
    tmp_path: Path, rows: int
) -> None:
    # Arrange — a one-row dataset can only yield an empty holdout.
    generated = generate("dummy_test_proj", tmp_path)
    module = _load_rendered_training(generated, "dummy_test_proj")
    dataset = module.pd.DataFrame({"pickup_count": range(rows)})

    # Act & Assert
    with pytest.raises(ValueError, match=f"{rows} rows"):
        module.DemandDatasetSplitter().split(dataset, test_size=0.2)


def test_rendered_split_holdout_is_the_tail_rows(tmp_path: Path) -> None:
    # Arrange
    generated = generate("dummy_test_proj", tmp_path)
    module = _load_rendered_training(generated, "dummy_test_proj")
    dataset = module.pd.DataFrame({"pickup_count": range(10)})

    # Act — ceil(10 * 0.25) = 3 rows form the holdout.
    train, holdout = module.DemandDatasetSplitter().split(
        dataset, test_size=0.25
    )

    # Assert
    assert len(train) == 7
    assert len(holdout) == 3
    assert list(holdout["pickup_count"]) == [7, 8, 9]


def test_rendered_split_keeps_one_train_row_under_large_test_size(
    tmp_path: Path,
) -> None:
    # Arrange
    generated = generate("dummy_test_proj", tmp_path)
    module = _load_rendered_training(generated, "dummy_test_proj")
    dataset = module.pd.DataFrame({"pickup_count": range(2)})

    # Act — the holdout clamps so the train frame stays non-empty.
    train, holdout = module.DemandDatasetSplitter().split(
        dataset, test_size=0.9
    )

    # Assert
    assert len(train) == 1
    assert len(holdout) == 1


def test_rendered_cli_config_error_exits_named(tmp_path: Path) -> None:
    # A rendered project's CLI must turn a loader error into a named exit,
    # not a raw interpreter traceback (G-307): the JSON log line still
    # carries the escaped exception, so pin the interpreter's own output.
    generated = generate("dummy_test_proj", tmp_path)
    config_path = generated / "configs" / "project.yaml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace(
            "year: 2023", "year: yes"
        ),
        encoding="utf-8",
    )

    # Act — run the real CLI entry point with the malformed config.
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "dummy_test_proj.interfaces.cli",
            "collect",
            "--config",
            "configs/project.yaml",
        ],
        cwd=generated,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONPATH": str(generated / "src")},
    )

    # Assert
    lines = result.stderr.splitlines()
    assert result.returncode == 1
    assert "Traceback (most recent call last):" not in lines
    assert lines[-1] == (
        "Invalid project config key year: expected integer, got True"
    )


def test_rendered_pipeline_stubs_exit_named(tmp_path: Path) -> None:
    # A rendered pipeline stub must fail loudly naming its command — never
    # exit 0 on a config-load-only body that logs a success line.
    generated = generate("dummy_test_proj", tmp_path)
    environment = {**os.environ, "PYTHONPATH": str(generated / "src")}

    for command in (
        "collect",
        "preprocess",
        "features",
        "train",
        "tune",
        "evaluate",
        "deploy",
        "monitor",
    ):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "dummy_test_proj.interfaces.cli",
                command,
                "--config",
                "configs/project.yaml",
            ],
            cwd=generated,
            capture_output=True,
            text=True,
            check=False,
            env=environment,
        )
        lines = result.stderr.splitlines()
        assert result.returncode == 1, command
        assert "Traceback (most recent call last):" not in lines
        assert lines[-1] == f"{command} pipeline is not implemented", command
        combined_output = result.stdout + result.stderr
        assert "pipeline_completed" not in combined_output, command


def test_rendered_domain_stubs_raise_not_implemented(tmp_path: Path) -> None:
    # Scaffolded domain classes must fail loudly, never fabricate
    # artifacts; the dead `source_url` config surface dies with them.
    generated = generate("dummy_test_proj", tmp_path)
    package = generated / "src" / "dummy_test_proj"

    stubs = {
        "data/collection.py": "TlcYellowTaxiParquetCollector.collect",
        "data/preprocessing.py": "YellowTaxiTripPreprocessor.preprocess",
        "data/supervised_dataset.py": "NextHourDemandDatasetBuilder.build",
        "features/feast_materialization.py": "LocalFeastMaterializer.apply",
        "features/hourly_demand.py": "HourlyDemandFeatureBuilder.build",
        "models/tuning.py": "DemandModelTuner.tune",
    }
    fabrications = {
        "data/collection.py": "_tripdata_",
        "data/preprocessing.py": ".to_parquet(",
        "data/supervised_dataset.py": ".to_parquet(",
        "features/feast_materialization.py": ".mkdir(",
        "features/hourly_demand.py": ".to_parquet(",
        "models/tuning.py": "return 1.0",
    }
    for relative_path, surface in stubs.items():
        source = (package / relative_path).read_text(encoding="utf-8")
        assert "raise NotImplementedError" in source, relative_path
        assert f'"{surface} is not implemented"' in source, relative_path
        assert fabrications[relative_path] not in source, relative_path

    configuration_source = (package / "configuration.py").read_text(
        encoding="utf-8"
    )
    project_yaml = (generated / "configs" / "project.yaml").read_text(
        encoding="utf-8"
    )
    assert "source_url" not in configuration_source
    assert "source_url" not in project_yaml


def test_pre_gen_hook_exits_clean_inside_rendered_tree(tmp_path: Path) -> None:
    # Arrange — render and run the hook exactly as cookiecutter does
    # (template → script, cwd = the just-created project dir) with a stray
    # `projects/<slug>` planted inside it: a probe scoped to the rendered
    # tree must not gate generation.
    rendered_dir = tmp_path / "rendered"
    (rendered_dir / "projects" / "dummy_test_proj").mkdir(parents=True)
    hook_source = (
        (TEMPLATE_DIR / "hooks" / "pre_gen_project.py")
        .read_text(encoding="utf-8")
        .replace("{{ cookiecutter.project_slug }}", "dummy_test_proj")
    )
    hook_script = tmp_path / "pre_gen_project.py"
    hook_script.write_text(hook_source, encoding="utf-8")

    # Act
    result = subprocess.run(
        [sys.executable, str(hook_script)],
        cwd=rendered_dir,
        capture_output=True,
        text=True,
        check=False,
    )

    # Assert
    assert result.returncode == 0, result.stderr + result.stdout


def test_generate_into_existing_directory_raises(tmp_path: Path) -> None:
    # Arrange — cookiecutter's own guard covers `<output_dir>/<slug>`
    # collisions before the pre_gen hook runs.
    generate("dummy_test_proj", tmp_path)

    # Act & Assert
    with pytest.raises(OutputDirExistsException):
        generate("dummy_test_proj", tmp_path)


def test_generate_rejects_invalid_slug(tmp_path: Path) -> None:
    # Act & Assert — the pre_gen hook still validates the slug pattern.
    with pytest.raises(FailedHookException):
        generate("9abc", tmp_path)


def _load_rendered_configuration(generated: Path, slug: str) -> ModuleType:
    module_path = generated / "src" / slug / "configuration.py"
    spec = importlib.util.spec_from_file_location(
        f"{slug}.configuration", module_path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_rendered_training(generated: Path, slug: str) -> ModuleType:
    module_path = generated / "src" / slug / "models" / "training.py"
    spec = importlib.util.spec_from_file_location(
        f"{slug}.models.training", module_path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _run_ruff(*arguments: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "--config",
            str(RUFF_CONFIG),
            *arguments,
        ],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
