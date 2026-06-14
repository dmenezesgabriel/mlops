from pathlib import Path
from typing import Protocol

from ssg.domain import Site


class SiteRepository(Protocol):
    def load(self, config_path: Path) -> Site: ...
