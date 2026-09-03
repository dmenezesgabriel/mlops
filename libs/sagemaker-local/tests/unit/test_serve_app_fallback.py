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
