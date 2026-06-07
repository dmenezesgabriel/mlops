from __future__ import annotations

from pathlib import Path

from videos.infrastructure.declarative.discovery import find_concept_yaml_files


class TestFindConceptYamlFiles:
    def test_returns_empty_for_nonexistent_dir(self) -> None:
        files = find_concept_yaml_files("/nonexistent/path")
        assert files == []

    def test_finds_yaml_files(self, tmp_path: Path) -> None:
        (tmp_path / "concept_a.yaml").write_text("concept:\n  id: a")
        (tmp_path / "concept_b.yml").write_text("concept:\n  id: b")
        (tmp_path / "not_concept.txt").write_text("hello")
        files = find_concept_yaml_files(tmp_path)
        paths = [str(p) for p in files]
        assert any("concept_a.yaml" in p for p in paths)
        assert any("concept_b.yml" in p for p in paths)
        assert not any("not_concept.txt" in p for p in paths)

    def test_sorts_files_by_name(self, tmp_path: Path) -> None:
        (tmp_path / "b.yaml").write_text("")
        (tmp_path / "a.yaml").write_text("")
        (tmp_path / "c.yaml").write_text("")
        files = find_concept_yaml_files(tmp_path)
        names = [p.name for p in files]
        assert names == ["a.yaml", "b.yaml", "c.yaml"]
