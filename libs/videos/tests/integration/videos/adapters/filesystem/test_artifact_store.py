from pathlib import Path

from videos.adapters.filesystem._artifact_store import FileSystemArtifactStore


class TestFileSystemArtifactStore:
    def test_write_preview_creates_file(self, tmp_path: Path) -> None:
        source = tmp_path / "source.mp4"
        source.write_text("fake video content")

        store = FileSystemArtifactStore(output_root=tmp_path)
        result = store.write_preview(source, "test_concept")

        assert result.exists()
        assert "previews" in str(result)

    def test_write_final_creates_file(self, tmp_path: Path) -> None:
        source = tmp_path / "source.mp4"
        source.write_text("fake video content")

        store = FileSystemArtifactStore(output_root=tmp_path)
        result = store.write_final(source, "test_concept")

        assert result.exists()
        assert "final" in str(result)

    def test_resolve_output_path_preview(self, tmp_path: Path) -> None:
        store = FileSystemArtifactStore(output_root=tmp_path)
        path = store.resolve_output_path("concept_a", "preview")
        assert "preview" in str(path)
        assert path.name == "concept_a.mp4"

    def test_resolve_output_path_final(self, tmp_path: Path) -> None:
        store = FileSystemArtifactStore(output_root=tmp_path)
        path = store.resolve_output_path("concept_b", "final")
        assert "final" in str(path)
        assert path.name == "concept_b.mp4"

    def test_creates_directories_on_init(self, tmp_path: Path) -> None:
        FileSystemArtifactStore(
            output_root=tmp_path,
            preview_subdir="previews",
            final_subdir="final",
        )
        assert (tmp_path / "previews").is_dir()
        assert (tmp_path / "final").is_dir()
