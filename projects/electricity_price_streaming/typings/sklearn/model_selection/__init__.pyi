"""Typed surface of scikit-learn's split helper used by train.py."""

from typing import TypeVar

_Array = TypeVar("_Array")

def train_test_split(
    *arrays: _Array,
    test_size: float | int | None = ...,
    train_size: float | int | None = ...,
    random_state: int | None = ...,
    shuffle: bool = ...,
    stratify: object = ...,
) -> list[_Array]: ...
