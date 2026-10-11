"""Shared fixture plumbing; the named fakes live in `tests/fakes.py`."""

from collections.abc import Iterator

import pytest
from fakes import reset_fake_state


@pytest.fixture(autouse=True)
def _reset_fake_state() -> Iterator[None]:
    reset_fake_state()
    yield
