from pathlib import Path

import pandas as pd
import pytest
from fakes import (
    FakeFeastModule,
    FakeFeatureStore,
    FakeMlflowModule,
    entity_frame,
    import_module_for,
    project_config,
    training_frame,
)
from nyc_taxi_demand_forecasting.models import training as training_module
from nyc_taxi_demand_forecasting.models.training import (
    DemandDatasetSplitter,
    DemandModelTrainer,
    PyfuncDemandModel,
    RidgeDemandRegressor,
)


def test_ridge_demand_regressor_predicts_target() -> None:
    # Arrange
    features = pd.DataFrame(
        {"pickup_count": [1.0, 2.0, 3.0], "hour": [0.0, 0.0, 0.0]}
    )
    target = pd.Series([3.0, 5.0, 7.0])

    # Act
    model = RidgeDemandRegressor(alpha=0.1).fit(features, target)
    predictions = model.predict(
        pd.DataFrame({"pickup_count": [4.0], "hour": [0.0]})
    )

    # Assert
    assert round(float(predictions.iloc[0]), 3) > 0.0


def test_ridge_demand_regressor_rejects_unfitted_prediction() -> None:
    # Arrange
    model = RidgeDemandRegressor()
    features = pd.DataFrame({"pickup_count": [1.0], "hour": [0.0]})

    # Act / Assert
    with pytest.raises(ValueError, match="expected fitted coefficients"):
        model.predict(features)


def test_pyfunc_demand_model_predicts_using_wrapped_model() -> None:
    # Arrange
    features = pd.DataFrame({"pickup_count": [1.0, 2.0], "hour": [0.0, 0.0]})
    target = pd.Series([3.0, 5.0])
    wrapped = RidgeDemandRegressor(alpha=1.0).fit(features, target)
    pyfunc_model = PyfuncDemandModel(wrapped)

    # Act
    predictions = pyfunc_model.predict(
        None, pd.DataFrame({"pickup_count": [3.0], "hour": [0.0]})
    )

    # Assert
    assert len(predictions) == 1


def test_demand_dataset_splitter_preserves_order() -> None:
    # Arrange
    dataset = pd.DataFrame({"pickup_count": [1, 2, 3, 4, 5]})

    # Act
    train_frame, test_frame = DemandDatasetSplitter().split(
        dataset, test_size=0.4
    )

    # Assert
    assert train_frame["pickup_count"].to_list() == [1, 2, 3]
    assert test_frame["pickup_count"].to_list() == [4, 5]


def test_trainer_trains_evaluates_and_logs_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    config = project_config(tmp_path)
    dataset_path = tmp_path / "entities.parquet"
    entity_frame().to_parquet(dataset_path, index=False)
    FakeFeatureStore.historical_result = training_frame()
    fake_mlflow = FakeMlflowModule()
    monkeypatch.setattr(
        training_module,
        "import_module",
        import_module_for({"feast": FakeFeastModule}),
    )
    monkeypatch.setattr(training_module, "mlflow", fake_mlflow)

    # Act
    metrics = DemandModelTrainer().train(
        dataset_path,
        config.paths.models,
        config.training,
        config.mlflow,
        config.feast,
        alpha=0.5,
    )

    # Assert
    assert metrics.mae >= 0
    store = FakeFeatureStore.instances[0]
    assert store.repo_path == str(config.feast.repo_path)
    assert fake_mlflow.params == {"alpha": 0.5}
    assert set(fake_mlflow.metrics) == {"mae", "rmse", "r2"}
    assert "model_summary.txt" in fake_mlflow.texts
    assert fake_mlflow.pyfunc.logged_models[0] == {
        "artifact_path": "model",
        "python_model": fake_mlflow.pyfunc.logged_models[0]["python_model"],
        "registered_model_name": "model",
    }
    assert isinstance(
        fake_mlflow.pyfunc.logged_models[0]["python_model"],
        PyfuncDemandModel,
    )
