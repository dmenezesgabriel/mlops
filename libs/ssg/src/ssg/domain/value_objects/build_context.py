from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ssg.application.ports.dependency_tracker import DependencyTracker


@dataclass(frozen=True)
class BuildContext:
    config_path: Path
    output_path: Path
    collection_name: str | None
    correlation_id: str
    dependency_tracker: "DependencyTracker | None" = None
