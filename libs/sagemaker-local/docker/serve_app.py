"""Minimal SageMaker hosting runtime for local mode.

Resolves the four callback-convention functions (model/input/predict/output)
from the user script at ``/opt/ml/code`` that ``SAGEMAKER_PROGRAM`` names,
falling back to joblib + CSV/JSON/npy defaults when the user script omits them.
SageMaker mounts the user script under its own filename (e.g. train.py), so
the module is loaded from that exact path rather than a fixed name.
"""

import importlib.util
import io
import json
import os

import flask
import joblib
import numpy as np

MODEL_DIR = "/opt/ml/model"
CODE_DIR = "/opt/ml/code"
CODE_FILENAME = os.environ.get("SAGEMAKER_PROGRAM", "inference.py")
_CODE_PATH = f"{CODE_DIR}/{CODE_FILENAME}"

app = flask.Flask("sagemaker-local")
inference_module: object | None = None
model: object | None = None
model_loaded: bool = False


def _load_inference_module():
    global inference_module
    if inference_module is None:
        if not os.path.exists(_CODE_PATH):
            # BYOC serving (generic Estimator) mounts no /opt/ml/code; fall back
            # entirely to the joblib + generic predict defaults.
            return None
        spec = importlib.util.spec_from_file_location(
            "user_script", _CODE_PATH
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        inference_module = module
    return inference_module


def _resolve(fn_name: str, default):
    module = _load_inference_module()
    if module is None:
        return default
    return getattr(module, fn_name, default)


def model_fn_default(model_dir: str):
    return joblib.load(f"{model_dir}/model.joblib")


def input_fn_default(content_type: str, body: bytes):
    if content_type.startswith("text/csv"):
        return np.genfromtxt(io.BytesIO(body), delimiter=",", dtype=np.float64)
    if content_type.startswith("application/json"):
        return np.asarray(json.loads(body.decode("utf-8")), dtype=np.float64)
    if content_type.startswith("application/x-npy"):
        return np.load(io.BytesIO(body), allow_pickle=False)
    return body


def predict_fn_default(data, model):
    return model.predict(data)


def output_fn_default(prediction, accept: str):
    arr = (
        np.asarray(prediction)
        if not isinstance(prediction, np.ndarray)
        else prediction
    )
    if accept.startswith("application/x-npy"):
        buf = io.BytesIO()
        np.save(buf, arr, allow_pickle=False)
        return app.response_class(
            buf.getvalue(), content_type="application/x-npy"
        )
    if accept.startswith("text/csv"):
        return app.response_class(
            np.array2string(arr, separator=","),
            content_type="text/csv",
        )
    return app.response_class(
        json.dumps(arr.tolist()), content_type="application/json"
    )


def _model_instance():
    global model, model_loaded
    if not model_loaded:
        model = _resolve("model_fn", model_fn_default)(MODEL_DIR)
        model_loaded = True
    return model


@app.get("/ping")
def ping():
    return "", 200


@app.post("/invocations")
def invocations():
    content_type = flask.request.content_type or "text/csv"
    accept = flask.request.headers.get("Accept", "application/json")
    data = _resolve("input_fn", input_fn_default)(
        content_type, flask.request.get_data()
    )
    prediction = _resolve("predict_fn", predict_fn_default)(
        data, _model_instance()
    )
    return _resolve("output_fn", output_fn_default)(prediction, accept)


def create_app():
    return app
