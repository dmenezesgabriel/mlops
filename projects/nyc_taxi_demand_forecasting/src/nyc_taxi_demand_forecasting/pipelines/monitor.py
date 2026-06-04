from pathlib import Path

from nyc_taxi_demand_forecasting.configuration import ProjectConfigLoader


def run(config_path: Path) -> None:
    config = ProjectConfigLoader().load(config_path)
    config.paths.reports.mkdir(parents=True, exist_ok=True)
    (config.paths.reports / "monitoring.md").write_text(
        "# Monitoring\n\nLocal monitoring checks are ready to be automated.\n",
        encoding="utf-8",
    )
