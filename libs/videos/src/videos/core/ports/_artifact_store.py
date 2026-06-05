from __future__ import annotations

from pathlib import Path
from typing import Protocol


class ArtifactStore(Protocol):
    def write_final(self, source_path: Path, concept_id: str) -> Path: ...

    def write_preview(self, source_path: Path, concept_id: str) -> Path: ...

    def resolve_output_path(self, concept_id: str, quality: str) -> Path: ...
