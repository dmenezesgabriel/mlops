from pathlib import Path
from typing import Protocol


class PreviewServer(Protocol):
    def serve(self, directory: Path, host: str, port: int) -> None: ...
