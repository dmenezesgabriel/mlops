"""Typed surface of scikit-learn's pipeline helpers used by train.py."""

import numpy as np
from numpy.typing import NDArray

class Pipeline:
    def fit(
        self, features: object, labels: object, **kwargs: object
    ) -> Pipeline: ...
    def predict(
        self, features: object, **kwargs: object
    ) -> NDArray[np.int64]: ...
    def predict_proba(
        self, features: object, **kwargs: object
    ) -> NDArray[np.float64]: ...

def make_pipeline(*steps: object, **kwargs: object) -> Pipeline: ...
