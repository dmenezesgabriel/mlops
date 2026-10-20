"""Typed surface of the scikit-learn dataset loader used by prepare_data.py."""

from typing import Literal, overload

import pandas as pd

class Bunch:
    data: pd.DataFrame
    target: pd.Series
    frame: pd.DataFrame
    DESCR: str
    details: dict[str, object]

@overload
def fetch_california_housing(
    *, as_frame: Literal[True] = ..., **kwargs: object
) -> Bunch: ...
@overload
def fetch_california_housing(
    *, as_frame: Literal[False], **kwargs: object
) -> tuple[pd.DataFrame, pd.Series]: ...
def fetch_california_housing(
    *, as_frame: bool = ..., **kwargs: object
) -> Bunch | tuple[pd.DataFrame, pd.Series]: ...
