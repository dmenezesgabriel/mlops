"""In-process unit tests for ``notebooks/_evidence.py`` — no stack required.

Loads the evidence module by file path (the notebooks directory is not a
package; notebook kernels resolve it via cwd instead). ``persist`` writes are
redirected to ``tmp_path`` by monkeypatching ``PROJECT_DIR``.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest

PROJECT_DIR = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "_evidence", PROJECT_DIR / "notebooks" / "_evidence.py"
)
assert _SPEC is not None and _SPEC.loader is not None
evidence = importlib.util.module_from_spec(_SPEC)
sys.modules["_evidence"] = evidence
_SPEC.loader.exec_module(evidence)


@pytest.fixture(autouse=True)
def _clear_evidence() -> Iterator[None]:
    evidence.EVIDENCE.clear()
    yield
    evidence.EVIDENCE.clear()


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "notebooks").mkdir()
    monkeypatch.setattr(evidence, "PROJECT_DIR", tmp_path)
    return tmp_path


def _notebook(project: Path, stem: str) -> None:
    (project / "notebooks" / f"{stem}.ipynb").write_text("{}")


def test_record_appends_and_returns_validated_row() -> None:
    row = evidence.record("endpoint routing", "PASS", "athena→:5001", 12.0)
    assert evidence.EVIDENCE == [row]
    assert row.feature == "endpoint routing"


def test_record_rejects_bad_status() -> None:
    with pytest.raises(ValueError, match="BOGUS"):
        evidence.record("feature", "BOGUS", "detail")


def test_evidence_construction_validates_status() -> None:
    with pytest.raises(ValueError, match="BOGUS"):
        evidence.Evidence(feature="x", status="BOGUS", detail="d")


def test_evidence_construction_rejects_non_str_fields() -> None:
    with pytest.raises(TypeError, match="detail"):
        evidence.Evidence(feature="x", status="PASS", detail=cast(str, 123))


def test_render_escapes_feature_cells() -> None:
    row = evidence.Evidence(feature="a | b\nc", status="PASS", detail="d | e")
    rendered = evidence.render([row])
    assert "| a \\| b c | PASS | d \\| e |  |" in rendered


def test_render_keeps_sub_millisecond_latency() -> None:
    row = evidence.Evidence(
        feature="f", status="PASS", detail="d", latency_ms=0.4
    )
    assert "| 0.4 |" in evidence.render([row])


def test_render_keeps_only_latest_row_per_probe() -> None:
    rows = [
        evidence.Evidence(
            feature="f", status="PASS", detail="d", latency_ms=1.0
        ),
        evidence.Evidence(
            feature="f", status="PASS", detail="d", latency_ms=2.0
        ),
    ]
    body = [
        line
        for line in evidence.render(rows).splitlines()
        if line.startswith("| f ")
    ]
    assert body == ["| f | PASS | d | 2 |"]


def test_persist_writes_fragment_and_index(project: Path) -> None:
    _notebook(project, "01_x")
    row = evidence.Evidence(feature="f", status="PASS", detail="d")
    fragment = evidence.persist("01_x", [row])
    assert fragment == project / "parity" / "01_x.md"
    assert fragment.exists()
    index_text = (project / "PARITY.md").read_text()
    assert "## 01_x" in index_text
    assert "| f | PASS | d |  |" in index_text


@pytest.mark.parametrize(
    "name", ["../escaped", "a/b", "Bad Name", "UPPER", ""]
)
def test_persist_rejects_non_slug_names(project: Path, name: str) -> None:
    with pytest.raises(ValueError, match=repr(name)):
        evidence.persist(name, [])
    assert not (project / "escaped.md").exists()
    assert not (project / "PARITY.md").exists()


def test_persist_drops_orphan_fragments(project: Path) -> None:
    _notebook(project, "01_x")
    parity_dir = project / "parity"
    parity_dir.mkdir()
    (parity_dir / "99_orphan.md").write_text("## 99_orphan\n\nstale\n")
    evidence.persist(
        "01_x", [evidence.Evidence(feature="f", status="PASS", detail="d")]
    )
    assert not (parity_dir / "99_orphan.md").exists()
    assert "99_orphan" not in (project / "PARITY.md").read_text()


def test_persist_leaves_no_tmp_files(project: Path) -> None:
    _notebook(project, "01_x")
    evidence.persist(
        "01_x", [evidence.Evidence(feature="f", status="PASS", detail="d")]
    )
    assert list((project / "parity").glob("*.tmp")) == []
    assert list(project.glob("*.tmp")) == []


def test_concurrent_persists_keep_all_sections(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _notebook(project, "01_a")
    _notebook(project, "02_b")
    index_write_started = threading.Event()
    other_writer_done = threading.Event()
    real_write_text = Path.write_text
    slow_thread: dict[str, int] = {}

    def stalled_write_text(
        self: Path, data: str, *args: Any, **kwargs: Any
    ) -> int:
        if self.name in {
            "PARITY.md",
            "PARITY.md.tmp",
        } and threading.get_ident() == slow_thread.get("id"):
            index_write_started.set()
            other_writer_done.wait(timeout=5)
        return real_write_text(self, data, *args, **kwargs)

    def run_first() -> None:
        slow_thread["id"] = threading.get_ident()
        evidence.persist(
            "01_a",
            [evidence.Evidence(feature="fa", status="PASS", detail="da")],
        )

    def run_second() -> None:
        assert index_write_started.wait(timeout=5)
        evidence.persist(
            "02_b",
            [evidence.Evidence(feature="fb", status="PASS", detail="db")],
        )
        other_writer_done.set()

    monkeypatch.setattr(Path, "write_text", stalled_write_text)
    first = threading.Thread(target=run_first)
    second = threading.Thread(target=run_second)
    first.start()
    second.start()
    first.join(timeout=15)
    second.join(timeout=15)
    assert not first.is_alive() and not second.is_alive()
    index_text = (project / "PARITY.md").read_text()
    assert "## 01_a" in index_text
    assert "## 02_b" in index_text


def test_render_default_reads_recorded_evidence() -> None:
    evidence.record("f", "PASS", "d")
    assert "| f | PASS | d |  |" in evidence.render()


def test_render_exact_table_shape() -> None:
    row = evidence.Evidence(
        feature="f", status="PASS", detail="d", latency_ms=1.0
    )
    assert evidence.render([row]) == (
        "| feature | status | detail | latency_ms |\n"
        "|---|---|---|---|\n"
        "| f | PASS | d | 1 |\n"
    )


def test_render_keeps_rows_differing_in_status_or_detail() -> None:
    rows = [
        evidence.Evidence(feature="f", status="PASS", detail="d"),
        evidence.Evidence(feature="f", status="FAIL", detail="d"),
        evidence.Evidence(feature="f", status="PASS", detail="e"),
    ]
    body = [
        line
        for line in evidence.render(rows).splitlines()
        if line.startswith("| f ")
    ]
    assert len(body) == 3


def test_persist_replaces_tmp_files_atomically(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _notebook(project, "01_x")
    replaced: list[tuple[str, str]] = []
    real_replace = os.replace

    def spy_replace(src: Path, dst: Path) -> None:
        replaced.append((src.name, dst.name))
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", spy_replace)
    evidence.persist(
        "01_x", [evidence.Evidence(feature="f", status="PASS", detail="d")]
    )
    assert ("01_x.md.tmp", "01_x.md") in replaced
    assert ("PARITY.md.tmp", "PARITY.md") in replaced


def test_index_sorts_glob_order(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _notebook(project, "01_a")
    _notebook(project, "02_b")
    real_glob = Path.glob

    def reversed_glob(self: Path, pattern: str) -> Iterator[Path]:
        return iter(list(real_glob(self, pattern))[::-1])

    monkeypatch.setattr(Path, "glob", reversed_glob)
    evidence.persist(
        "02_b", [evidence.Evidence(feature="fb", status="PASS", detail="db")]
    )
    evidence.persist(
        "01_a", [evidence.Evidence(feature="fa", status="PASS", detail="da")]
    )
    index_text = (project / "PARITY.md").read_text()
    assert index_text.index("## 01_a") < index_text.index("## 02_b")


def test_index_carries_generated_header(project: Path) -> None:
    _notebook(project, "01_x")
    evidence.persist(
        "01_x", [evidence.Evidence(feature="f", status="PASS", detail="d")]
    )
    index_text = (project / "PARITY.md").read_text()
    assert index_text.startswith("# Athena emulator parity evidence\n\n")
    assert "do not edit by hand" in index_text
