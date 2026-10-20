"""Typed surface of scikit-learn's preprocessing used by train.py."""

import numpy as np
from numpy.typing import NDArray

class StandardScaler:
    def __init__(self, **kwargs: object) -> None: ...
    def fit(self, features: object, **kwargs: object) -> StandardScaler: ...
    def transform(
        self, features: object, **kwargs: object
    ) -> NDArray[np.float64]: ...
    def fit_transform(
        self, features: object, **kwargs: object
    ) -> NDArray[np.float64]: ...
