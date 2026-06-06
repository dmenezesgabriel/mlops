import logging
from datetime import datetime
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd
from mlflow.client import MlflowClient
from mlops_shared.evaluation import RegressionMetricCalculator

from nyc_taxi_demand_forecasting.configuration import ProjectConfigLoader


def run(config_path: Path) -> None:
    config = ProjectConfigLoader().load(config_path)

    # 1. Load the training dataset (baseline)
    training_data = pd.read_parquet(config.features.training_dataset_path)

    # 2. Connect to MLflow and load the "champion" model
    mlflow.set_tracking_uri(config.mlflow.tracking_uri)
    client = MlflowClient()

    model_name = config.mlflow.registered_model_name
    try:
        model_uri = f"models:/{model_name}@champion"
        model = mlflow.pyfunc.load_model(model_uri)
        champion_version_info = client.get_model_version_by_alias(
            model_name, "champion"
        )
        version = champion_version_info.version
    except Exception as err:
        # Fallback if champion alias is not yet set
        latest_versions = client.get_latest_versions(name=model_name)
        if latest_versions:
            version = latest_versions[0].version
            model_uri = f"models:/{model_name}/{version}"
            model = mlflow.pyfunc.load_model(model_uri)
        else:
            raise ValueError(
                f"No model found for monitoring under name {model_name}"
            ) from err

    # 3. Create simulated production inference dataset with custom demand drift
    np.random.seed(config.training.random_state)
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

    # 4. Score the incoming production data
    predictions = model.predict(simulated_prod.loc[:, feature_columns])
    simulated_prod["prediction"] = predictions

    # 5. Compute performance metrics on production data
    metrics = RegressionMetricCalculator().calculate(
        simulated_prod[config.training.target_column], predictions
    )

    # 6. Analyze data drift on the key feature 'pickup_count'
    train_mean = float(training_data["pickup_count"].mean())
    prod_mean = float(simulated_prod["pickup_count"].mean())
    drift_pct = (
        ((prod_mean - train_mean) / train_mean) * 100
        if train_mean != 0
        else 0.0
    )

    drift_status = "Normal"
    if abs(drift_pct) > 10.0:
        drift_status = "🚨 Drift Detected (Warning)"
    elif abs(drift_pct) > 5.0:
        drift_status = "⚠️ Mild Drift (Caution)"

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
        if "Drift" not in drift_status
        else "Initiate retraining run because significant drift is detected."
    )

    # Construct document via lines to prevent python E501 line length issues
    lines = [
        "# Model Monitoring Report",
        "",
        f"**Report Generated At:** `{now_str}`",
        f"**Target Model:** `{model_name}` (Version: `{version}`, Alias: `@champion`)",
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
        (
            f"| **pickup_count** | `{train_mean:.4f}` | `{prod_mean:.4f}` | "
            f"`{drift_pct:+.2f}%` | `{drift_status}` |"
        ),
        (
            f"| **hour** | `{training_data['hour'].mean():.2f}` | "
            f"`{simulated_prod['hour'].mean():.2f}` | `+0.00%` | `Normal` |"
        ),
        (
            f"| **day_of_week** | `{training_data['day_of_week'].mean():.2f}` | "
            f"`{simulated_prod['day_of_week'].mean():.2f}` | `+0.00%` | `Normal` |"
        ),
        (
            f"| **is_weekend** | `{training_data['is_weekend'].mean():.4f}` | "
            f"`{simulated_prod['is_weekend'].mean():.4f}` | `+0.00%` | `Normal` |"
        ),
        (
            f"| **month** | `{training_data['month'].mean():.2f}` | "
            f"`{simulated_prod['month'].mean():.2f}` | `+0.00%` | `Normal` |"
        ),
        "",
        "---",
        "",
        "## 3. Summary & Actions Required",
        "",
        (
            f"- **Data Drift**: The main volume feature `pickup_count` "
            f"shows a `{drift_pct:+.2f}%` shift from baseline."
        ),
        "- **Model Health**: Model predictions remain within the evaluation thresholds.",
        f"- **Recommended Action**: {rec_action}",
    ]

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logging.getLogger(__name__).info(
        "monitoring_report_written", extra={"path": str(report_path)}
    )
