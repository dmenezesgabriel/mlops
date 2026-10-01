from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class PreviewServer(Protocol):
    def serve(self, directory: Path, host: str, port: int) -> None: ...

    def trigger_reload(self) -> None: ...
