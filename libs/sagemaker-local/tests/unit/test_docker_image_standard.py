"""Contract tests for the SageMaker image standard.

This package owns the shared ``serve`` assets and the per-image dependency
locks, so it also pins the nine Dockerfiles against that standard
(ADR-0014, ADR-0015). The checks are file reads: no docker daemon needed.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
REQUIREMENTS_DIR = REPO_ROOT / "libs/sagemaker-local/docker/requirements"

DOCKERFILES = {
    "standard": "libs/sagemaker-local/docker/Dockerfile",
    "california-train": "projects/california_house_pricing/Dockerfile",
    "california-inference": (
        "projects/california_house_pricing/Dockerfile.inference"
    ),
    "electricity-train": "projects/electricity_price_streaming/Dockerfile",
    "electricity-inference": (
        "projects/electricity_price_streaming/Dockerfile.inference"
    ),
    "telco-train": "projects/telco_customer_churn/Dockerfile",
    "telco-inference": "projects/telco_customer_churn/Dockerfile.inference",
    "wine-train": "projects/wine_quality_classification/Dockerfile",
    "wine-inference": (
        "projects/wine_quality_classification/Dockerfile.inference"
    ),
}
TRAIN_VARIANTS = [
    "standard",
    "california-train",
    "electricity-train",
    "telco-train",
    "wine-train",
]
INFERENCE_VARIANTS = [
    "california-inference",
    "electricity-inference",
    "telco-inference",
    "wine-inference",
]
ALL_VARIANTS = TRAIN_VARIANTS + INFERENCE_VARIANTS

# Measured 2026-10-21: these two are sdist-only on PyPI for CPython 3.12;
# every other runtime requirement has a manylinux_2_28 wheel.
SDIST_ONLY_PACKAGES = ["sagemaker-training", "inotify-simple"]

FRAMEWORKS = {
    "standard": ["xgboost==2.1.4", "lightgbm==4.6.0", "catboost==1.2.7"],
    "california": ["lightgbm==4.6.0"],
    "electricity": ["catboost==1.2.7"],
    "telco": ["xgboost==2.1.4"],
    "wine": ["scikit-learn==1.6.1"],
}

BASE_IMAGE = re.compile(
    r"^FROM python:3\.12-slim@sha256:[0-9a-f]{64}$", re.MULTILINE
)
LABEL_KEYS = [
    "org.opencontainers.image.title",
    "org.opencontainers.image.source",
    "org.opencontainers.image.revision",
    "org.opencontainers.image.licenses",
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _input_requirements(variant: str) -> list[str]:
    lines = [
        line.strip()
        for line in _read(REQUIREMENTS_DIR / f"{variant}.in").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert lines, f"{variant}.in has no requirements"
    for line in lines:
        assert "==" in line, (
            f"{variant}.in has an unpinned requirement: {line}"
        )
    return [line.split("==", 1)[0] for line in lines]


def _hashed_requirements(lock_text: str) -> dict[str, int]:
    hashes: dict[str, int] = {}
    current: str | None = None
    for line in lock_text.splitlines():
        if line.startswith("--"):
            current = None
            continue
        if line and not line.startswith((" ", "#")):
            if "==" not in line:
                current = None
                continue
            current = line.split("==", 1)[0]
            hashes[current] = 0
            continue
        if current is not None and "--hash=sha256:" in line:
            hashes[current] += 1
    return hashes


@pytest.mark.parametrize("variant", ALL_VARIANTS)
def test_lock_file_hashes_every_requirement(variant: str) -> None:
    hashes = _hashed_requirements(_read(REQUIREMENTS_DIR / f"{variant}.txt"))
    assert hashes, f"{variant}.txt has no pinned requirements"
    for name in _input_requirements(variant):
        assert hashes.get(name, 0) > 0, f"{variant}.txt has no hash for {name}"


@pytest.mark.parametrize("variant", ALL_VARIANTS)
def test_lock_file_declares_the_measured_sdist_policy(variant: str) -> None:
    lines = _read(REQUIREMENTS_DIR / f"{variant}.txt").splitlines()
    options = [line for line in lines if line.startswith("--")]
    if variant in INFERENCE_VARIANTS:
        assert "--only-binary :all:" in options
        assert not any(line.startswith("--no-binary") for line in options)
        return
    for package in SDIST_ONLY_PACKAGES:
        assert f"--no-binary {package}" in options
    # A trailing --only-binary cancels the per-package exceptions in pip.
    assert "--only-binary :all:" not in options


@pytest.mark.parametrize("variant", TRAIN_VARIANTS)
def test_train_locks_ship_sagemaker_training(variant: str) -> None:
    lock = _read(REQUIREMENTS_DIR / f"{variant}.txt")
    assert "sagemaker-training==5.1.1" in lock


@pytest.mark.parametrize("variant", INFERENCE_VARIANTS)
def test_inference_locks_drop_sagemaker_training(variant: str) -> None:
    lock = _read(REQUIREMENTS_DIR / f"{variant}.txt")
    assert "sagemaker-training==" not in lock


@pytest.mark.parametrize("variant", ALL_VARIANTS)
def test_lock_pins_the_image_framework(variant: str) -> None:
    family = variant.removesuffix("-train").removesuffix("-inference")
    lock = _read(REQUIREMENTS_DIR / f"{variant}.txt")
    for framework in FRAMEWORKS[family]:
        assert framework in lock, f"{variant}.txt is missing {framework}"


@pytest.mark.parametrize("variant", ALL_VARIANTS)
def test_dockerfile_uses_the_hash_locked_requirements(variant: str) -> None:
    text = _read(REPO_ROOT / DOCKERFILES[variant])
    assert BASE_IMAGE.search(text), f"{variant}: base image is not pinned"
    assert f"requirements/{variant}.txt" in text, variant
    assert "--require-hashes" in text, variant
    for key in LABEL_KEYS:
        assert key in text, f"{variant}: missing {key}"
    assert not re.search(r"^USER\s", text, re.MULTILINE), variant
    assert "SageMaker" in text and "root" in text, variant


@pytest.mark.parametrize(
    "makefile",
    [
        "projects/california_house_pricing/Makefile",
        "projects/electricity_price_streaming/Makefile",
        "projects/telco_customer_churn/Makefile",
        "projects/wine_quality_classification/Makefile",
    ],
)
def test_project_makefiles_pass_the_git_revision(makefile: str) -> None:
    text = _read(REPO_ROOT / makefile)
    assert "--build-arg GIT_REVISION=$(GIT_REVISION)" in text


def test_every_variant_has_an_input_and_a_lock() -> None:
    inputs = {path.stem for path in REQUIREMENTS_DIR.glob("*.in")}
    locks = {path.stem for path in REQUIREMENTS_DIR.glob("*.txt")}
    assert inputs == set(ALL_VARIANTS)
    assert locks == set(ALL_VARIANTS)
