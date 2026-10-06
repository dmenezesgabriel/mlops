import pandas as pd
import pytest
from ml_specialization.models.training import DemandDatasetSplitter


def _dataset(rows: int) -> pd.DataFrame:
    return pd.DataFrame({"pickup_count": range(rows)})


@pytest.mark.parametrize("test_size", [0.0, 1.0, 1.5, -0.1])
def test_split_rejects_out_of_range_test_size(test_size: float) -> None:
    # Arrange
    dataset = _dataset(10)

    # Act / Assert — degenerate ratios must not silently split.
    with pytest.raises(ValueError, match=f"test_size {test_size}"):
        DemandDatasetSplitter().split(dataset, test_size)


@pytest.mark.parametrize("rows", [0, 1])
def test_split_rejects_unsplittable_dataset(rows: int) -> None:
    # Arrange — a split that would leave an empty frame is an error.
    dataset = _dataset(rows)

    # Act / Assert
    with pytest.raises(ValueError, match=f"{rows} rows"):
        DemandDatasetSplitter().split(dataset, test_size=0.2)


def test_split_holdout_is_the_tail_rows() -> None:
    # Arrange
    dataset = _dataset(10)

    # Act — ceil(10 * 0.25) = 3 rows form the holdout.
    train, holdout = DemandDatasetSplitter().split(dataset, test_size=0.25)

    # Assert
    assert len(train) == 7
    assert len(holdout) == 3
    assert list(holdout["pickup_count"]) == [7, 8, 9]


def test_split_keeps_one_train_row_under_large_test_size() -> None:
    # Arrange
    dataset = _dataset(2)

    # Act — the holdout clamps so the train frame stays non-empty.
    train, holdout = DemandDatasetSplitter().split(dataset, test_size=0.9)

    # Assert
    assert len(train) == 1
    assert len(holdout) == 1
