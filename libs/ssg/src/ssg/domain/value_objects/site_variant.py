from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ssg.domain.entities.site import Site


@dataclass(frozen=True)
class SiteVariant:
    site: "Site"
    output_path: Path
