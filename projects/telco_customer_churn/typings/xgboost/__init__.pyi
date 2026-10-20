"""Typed surface of the XGBoost classifier used by the SageMaker entrypoint.

XGBoost ships no ``py.typed`` marker and lives only in the training image,
so this project-owned stub declares the members ``train.py`` calls.
"""

import numpy as np
from numpy.typing import NDArray

class XGBClassifier:
    def __init__(self, **kwargs: object) -> None: ...
    def fit(
        self, features: object, labels: object, **kwargs: object
    ) -> XGBClassifier: ...
    def predict(
        self, features: object, **kwargs: object
    ) -> NDArray[np.int64]: ...
    def predict_proba(
        self, features: object, **kwargs: object
    ) -> NDArray[np.float64]: ...
