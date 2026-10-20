"""Typed surface of the scikit-learn dataset loader used by prepare_data.py."""

from typing import Literal, overload

import pandas as pd

class Bunch:
    data: pd.DataFrame
    target: pd.Series
    frame: pd.DataFrame
    feature_names: list[str]
    target_names: list[str]
    DESCR: str
    details: dict[str, object]

@overload
def load_wine(*, as_frame: Literal[True] = ..., **kwargs: object) -> Bunch: ...
@overload
def load_wine(
    *, as_frame: Literal[False], **kwargs: object
) -> tuple[pd.DataFrame, pd.Series]: ...
def load_wine(
    *, as_frame: bool = ..., **kwargs: object
) -> Bunch | tuple[pd.DataFrame, pd.Series]: ...
