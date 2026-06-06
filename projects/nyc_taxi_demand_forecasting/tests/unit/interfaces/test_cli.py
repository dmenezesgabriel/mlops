from nyc_taxi_demand_forecasting.interfaces.cli import (
    create_parser,
    create_registry,
)


def test_cli_parser_accepts_pipeline_subcommands() -> None:
    # Arrange
    parser = create_parser()

    # Act
    arguments = parser.parse_args(
        ["collect", "--config", "configs/project.yaml"]
    )

    # Assert
    assert arguments.command == "collect"


def test_pipeline_command_registry_reports_invalid_command() -> None:
    # Arrange
    registry = create_registry()

    # Act
    command_names = registry.names()

    # Assert
    assert "train" in command_names
