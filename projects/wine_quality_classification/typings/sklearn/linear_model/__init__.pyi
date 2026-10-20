"""Typed surface of the scikit-learn classifier used by train.py."""

import numpy as np
from numpy.typing import NDArray

class LogisticRegression:
    def __init__(self, **kwargs: object) -> None: ...
    def fit(
        self, features: object, labels: object, **kwargs: object
    ) -> LogisticRegression: ...
    def predict(
        self, features: object, **kwargs: object
    ) -> NDArray[np.int64]: ...
    def predict_proba(
        self, features: object, **kwargs: object
    ) -> NDArray[np.float64]: ...
