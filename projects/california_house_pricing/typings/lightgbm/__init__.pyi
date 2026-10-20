"""Typed surface of the LightGBM estimator used by the SageMaker entrypoint.

LightGBM ships no ``py.typed`` marker and lives only in the training image,
so this project-owned stub declares the members ``train.py`` calls.
"""

import numpy as np
from numpy.typing import NDArray

class LGBMRegressor:
    def __init__(self, **kwargs: object) -> None: ...
    def fit(
        self, features: object, labels: object, **kwargs: object
    ) -> LGBMRegressor: ...
    def predict(
        self, features: object, **kwargs: object
    ) -> NDArray[np.float64]: ...
