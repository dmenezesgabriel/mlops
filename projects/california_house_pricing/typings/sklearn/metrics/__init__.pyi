"""Typed surface of the scikit-learn metrics used by train.py."""

from collections.abc import Iterable

def mean_absolute_error(
    y_true: Iterable[object],
    y_pred: Iterable[object],
    **kwargs: object,
) -> float: ...
def r2_score(
    y_true: Iterable[object],
    y_pred: Iterable[object],
    **kwargs: object,
) -> float: ...
