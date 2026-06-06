import pandas as pd
import pytest
from nyc_taxi_demand_forecasting.models.training import (
    DemandDatasetSplitter,
    LinearDemandRegressor,
    PyfuncDemandModel,
    RidgeDemandRegressor,
)


def test_linear_demand_regressor_predicts_linear_target() -> None:
    # Arrange
    features = pd.DataFrame(
        {"pickup_count": [1.0, 2.0, 3.0], "hour": [0.0, 0.0, 0.0]}
    )
    target = pd.Series([3.0, 5.0, 7.0])

    # Act
    model = LinearDemandRegressor().fit(features, target)
    predictions = model.predict(
        pd.DataFrame({"pickup_count": [4.0], "hour": [0.0]})
    )

    # Assert
    assert round(float(predictions.iloc[0]), 6) == 9.0


def test_linear_demand_regressor_rejects_unfitted_prediction() -> None:
    # Arrange
    model = LinearDemandRegressor()
    features = pd.DataFrame({"pickup_count": [1.0], "hour": [0.0]})

    # Act / Assert
    with pytest.raises(ValueError, match="expected fitted coefficients"):
        model.predict(features)


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
