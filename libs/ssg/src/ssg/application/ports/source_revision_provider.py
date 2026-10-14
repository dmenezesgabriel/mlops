from datetime import date
from pathlib import Path
from typing import Protocol


class SourceRevisionProvider(Protocol):
    """Version-control facts about an authored source file.

    Both lookups degrade to ``None`` — a build running outside a working
    tree (exported tarball, unreadable git) simply omits the dependent
    element rather than failing.
    """

    def newest_commit_date(self, path: Path) -> date | None: ...
    def repository_path(self, path: Path) -> str | None: ...
