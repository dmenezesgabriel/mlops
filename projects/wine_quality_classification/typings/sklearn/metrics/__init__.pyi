"""Typed surface of the scikit-learn metrics used by train.py."""

from collections.abc import Iterable

def accuracy_score(
    y_true: Iterable[object],
    y_pred: Iterable[object],
    *,
    normalize: bool = ...,
    sample_weight: object = ...,
) -> float: ...
