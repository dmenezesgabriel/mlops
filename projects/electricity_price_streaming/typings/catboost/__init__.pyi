"""Typed surface of the CatBoost estimator used by the SageMaker entrypoint.

CatBoost ships no ``py.typed`` marker and is not installed in the workspace
(it lives in the training image), so this project-owned stub declares only
the members ``train.py`` calls.
"""

import numpy as np
from numpy.typing import NDArray

class CatBoostClassifier:
    def __init__(self, **kwargs: object) -> None: ...
    def fit(
        self, features: object, labels: object, **kwargs: object
    ) -> CatBoostClassifier: ...
    def predict(
        self, features: object, **kwargs: object
    ) -> NDArray[np.int64]: ...
    def predict_proba(
        self, features: object, **kwargs: object
    ) -> NDArray[np.float64]: ...
