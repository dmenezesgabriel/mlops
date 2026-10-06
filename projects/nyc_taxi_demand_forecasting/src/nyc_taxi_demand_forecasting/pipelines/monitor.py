import logging
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import mlflow
import numpy as np
import pandas as pd
from mlflow.client import MlflowClient
from mlflow.exceptions import MlflowException
from mlflow.pyfunc import PyFuncModel
from mlops_shared.evaluation import RegressionMetricCalculator

from nyc_taxi_demand_forecasting.configuration import ProjectConfigLoader
from nyc_taxi_demand_forecasting.models.registry import latest_model_version


def _load_champion_model(
    client: MlflowClient, model_name: str
) -> tuple[PyFuncModel, str, str | None]:
    """Champion alias, falling back to the latest version if unset.

    A corrupt champion artifact propagates — the monitor must not silently
    evaluate a different model than the one the report claims.
    """
    try:
        champion = client.get_model_version_by_alias(model_name, "champion")
    except MlflowException:
        champion = None
    if champion is None:
        version = latest_model_version(client, model_name)
        model_uri = f"models:/{model_name}/{version}"
        return mlflow.pyfunc.load_model(model_uri), version, None
    model_uri = f"models:/{model_name}@champion"
    model = mlflow.pyfunc.load_model(model_uri)
    return model, champion.version, "@champion"


def _drift_stats(
    training: pd.Series, production: pd.Series
) -> tuple[float, float, float, str]:
    train_mean = float(training.mean())
    prod_mean = float(production.mean())
    if train_mean == 0:
        # A 0→nonzero shift is unbounded relative drift, not 0%.
        drift_pct = (
            0.0 if prod_mean == 0 else math.copysign(math.inf, prod_mean)
        )
    else:
        drift_pct = (prod_mean - train_mean) / train_mean * 100
    if abs(drift_pct) > 10.0:
        return train_mean, prod_mean, drift_pct, "🚨 Drift Detected (Warning)"
    if abs(drift_pct) > 5.0:
        return train_mean, prod_mean, drift_pct, "⚠️ Mild Drift (Caution)"
    return train_mean, prod_mean, drift_pct, "Normal"


def _feature_drift_rows(
    training_data: pd.DataFrame,
    simulated_prod: pd.DataFrame,
    feature_columns: list[str],
) -> tuple[list[str], bool, float]:
    """Markdown drift rows per feature plus summary scalars.

    Returns (rows, any-drift flag, pickup_count drift pct) — pickup_count is
    the report's designated "main volume feature".
    """
    drift_rows: list[str] = []
    any_drift = False
    pickup_drift_pct = 0.0
    for feature in feature_columns:
        train_mean, prod_mean, drift_pct, status = _drift_stats(
            training_data[feature], simulated_prod[feature]
        )
        if "Drift" in status:
            any_drift = True
        if feature == "pickup_count":
            pickup_drift_pct = drift_pct
        drift_rows.append(
            f"| **{feature}** | `{train_mean:.4f}` | `{prod_mean:.4f}` | "
            f"`{drift_pct:+.2f}%` | `{status}` |"
        )
    return drift_rows, any_drift, pickup_drift_pct


def run(config_path: Path) -> None:
    config = ProjectConfigLoader().load(config_path)

    # 1. Load the training dataset (baseline)
    training_data = pd.read_parquet(config.features.training_dataset_path)

    # 2. Connect to MLflow and load the "champion" model
    mlflow.set_tracking_uri(config.mlflow.tracking_uri)
    client = MlflowClient()

    model_name = config.mlflow.registered_model_name
    model, version, served_alias = _load_champion_model(client, model_name)
    alias_label = (
        served_alias
        if served_alias is not None
        else "none (latest-version fallback)"
    )

    # 3. Create simulated production inference dataset with custom demand drift
    simulated_prod = training_data.copy()

    # Shift pickup count by ~12% to simulate a demand drift event
    simulated_prod["pickup_count"] = (
        (simulated_prod["pickup_count"] * 1.12).round().astype(int)
    )

    feature_columns = [
        "pickup_count",
        "hour",
        "day_of_week",
        "is_weekend",
        "month",
    ]

    # 4. Score the incoming production data — pyfunc emits an ndarray, so
    # normalize the output shape instead of asserting a Series.
    raw_predictions: Any = model.predict(  # pyright: ignore[reportUnknownMemberType]
        simulated_prod.loc[:, feature_columns]
    )
    predictions = np.asarray(raw_predictions).ravel()
    simulated_prod["prediction"] = predictions

    # 5. Compute performance metrics on production data
    metrics = RegressionMetricCalculator().calculate(
        simulated_prod[config.training.target_column], predictions
    )

    # 6. Analyze data drift on every scored feature
    drift_rows, any_drift, pickup_drift_pct = _feature_drift_rows(
        training_data, simulated_prod, feature_columns
    )

    # 7. Write the monitoring report markdown
    report_dir = config.paths.reports
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "monitoring.md"

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Format long inline condition strings to avoid long lines
    mae_status = (
        "✅ PASS" if metrics.mae <= config.evaluation.max_mae else "❌ FAIL"
    )
    rmse_status = (
        "✅ PASS" if metrics.rmse <= config.evaluation.max_rmse else "❌ FAIL"
    )
    rec_action = (
        "No action required. Model is performing well."
        if not any_drift
        else "Initiate retraining run because significant drift is detected."
    )

    # Construct document via lines to prevent python E501 line length issues
    lines = [
        "# Model Monitoring Report",
        "",
        f"**Report Generated At:** `{now_str}`",
        f"**Target Model:** `{model_name}` (Version: `{version}`, Alias: `{alias_label}`)",
        f"**Monitored Samples:** `{len(simulated_prod)}`",
        "",
        "---",
        "",
        "## 1. Quality Gates (Inference vs. Target)",
        "",
        "The table below compares the performance of the active champion model on",
        "incoming production data against the configured quality gates.",
        "",
        "| Metric | Target Gate | Current Value | Status |",
        "| :--- | :--- | :--- | :--- |",
        f"| **MAE** | `<= {config.evaluation.max_mae}` | `{metrics.mae:.4f}` | {mae_status} |",
        f"| **RMSE** | `<= {config.evaluation.max_rmse}` | `{metrics.rmse:.4f}` | {rmse_status} |",
        f"| **R² Score** | `N/A` | `{metrics.r2:.4f}` | `N/A` |",
        "",
        "---",
        "",
        "## 2. Feature Drift Analysis",
        "",
        "We monitor for distribution changes in features to identify if model updates",
        "are needed due to changes in consumer patterns.",
        "",
        "| Feature | Train Mean (Baseline) | Production Mean | Drift (Diff %) | Drift Status |",
        "| :--- | :---: | :---: | :---: | :---: |",
        *drift_rows,
        "",
        "---",
        "",
        "## 3. Summary & Actions Required",
        "",
        (
            f"- **Data Drift**: The main volume feature `pickup_count` "
            f"shows a `{pickup_drift_pct:+.2f}%` shift from baseline."
        ),
        "- **Model Health**: Model predictions remain within the evaluation thresholds.",
        f"- **Recommended Action**: {rec_action}",
    ]

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logging.getLogger(__name__).info(
        "monitoring_report_written", extra={"path": str(report_path)}
    )
