"""Unit tests for the docker serve_app runtime (missing-script fallback).

serve_app.py lives under ``docker/`` as an image asset, not inside the installed
package, so each test imports a fresh module copy from that file path.
"""

from __future__ import annotations

import importlib.util
import os
import tempfile
import types
from pathlib import Path

import numpy as np
import pytest
from sagemaker_local.images import dockerfile_dir


def _load_serve_app(program: str) -> types.ModuleType:
    os.environ["SAGEMAKER_PROGRAM"] = program
    path = dockerfile_dir() / "serve_app.py"
    spec = importlib.util.spec_from_file_location("_serve_app_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class TestMissingScriptFallback:
    """BYOC serving mounts no /opt/ml/code; defaults must still apply."""

    def test_load_inference_module_returns_none_when_script_absent(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        module = _load_serve_app("train.py")
        monkeypatch.setattr(module, "_CODE_PATH", "/nonexistent/train.py")

        assert module._load_inference_module() is None

    def test_resolve_uses_default_when_script_absent(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        module = _load_serve_app("train.py")
        monkeypatch.setattr(module, "_CODE_PATH", "/nonexistent/train.py")

        default = object()
        assert module._resolve("predict_fn", default) is default

    def test_resolve_returns_script_function_when_present(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        module = _load_serve_app("train.py")
        default = object()
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "train.py"
            script.write_text("def custom_fn(): return 'custom'\n")
            monkeypatch.setattr(module, "_CODE_PATH", str(script))
            monkeypatch.setattr(module, "inference_module", None)

            handler = module._resolve("custom_fn", default)
            assert handler is not default
            assert handler() == "custom"


class TestExecutionParameters:
    """The local batch-transform flow queries /execution-parameters (see
    sagemaker.local.entities._LocalTransformJob.start) and falls back to SDK
    defaults on a non-200. A production server declares its batch contract."""

    def test_get_execution_parameters_reports_batch_contract(self):
        module = _load_serve_app("train.py")

        response = module.app.test_client().get("/execution-parameters")

        assert response.status_code == 200
        assert response.get_json() == {
            "BatchStrategy": "MultiRecord",
            "MaxPayloadInMB": 6,
        }


class TestOutputFnCsvContract:
    """``Accept: text/csv`` must emit the sagemaker-inference ``_array_to_csv``
    contract — ``np.savetxt`` rows (one value per line for 1-D, comma-joined
    rows for 2-D) — not a bracketed, line-wrapped ``np.array2string``."""

    def test_one_dimensional_prediction_emits_one_value_per_line(self):
        module = _load_serve_app("train.py")

        response = module.output_fn_default(np.array([1.0, 2.0]), "text/csv")

        assert response.get_data(as_text=True) == "1.0\n2.0\n"

    def test_two_dimensional_prediction_emits_comma_joined_rows(self):
        module = _load_serve_app("train.py")

        response = module.output_fn_default(
            np.array([[1.0, 2.0], [3.0, 4.0]]), "text/csv"
        )

        assert response.get_data(as_text=True) == "1.0,2.0\n3.0,4.0\n"

    def test_long_prediction_is_not_wrapped_and_round_trips(self):
        module = _load_serve_app("train.py")

        response = module.output_fn_default(np.arange(40.0), "text/csv")

        body = response.get_data()
        assert len(body.decode("utf-8").splitlines()) == 40
        parsed = module.input_fn_default("text/csv", body)
        np.testing.assert_array_equal(parsed, np.arange(40.0))

    def test_invocations_with_accept_csv_returns_csv_rows(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        module = _load_serve_app("train.py")
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "train.py"
            script.write_text(
                "import numpy as np\n"
                "def model_fn(model_dir): return object()\n"
                "def predict_fn(data, model): return np.array([1.0, 2.0])\n"
            )
            monkeypatch.setattr(module, "_CODE_PATH", str(script))
            monkeypatch.setattr(module, "inference_module", None)

            response = module.app.test_client().post(
                "/invocations",
                data=b"0.5\n1.5\n",
                content_type="text/csv",
                headers={"Accept": "text/csv"},
            )

        assert response.status_code == 200
        assert response.get_data(as_text=True) == "1.0\n2.0\n"
