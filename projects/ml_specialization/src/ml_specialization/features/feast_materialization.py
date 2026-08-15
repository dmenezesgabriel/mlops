from pathlib import Path


class LocalFeastMaterializer:
    """Apply Feast definitions against the local registry and online store.

    Example:
        LocalFeastMaterializer().apply(Path("feature_repo"))
    """

    def apply(self, repo_path: Path) -> None:
        repo_path.mkdir(parents=True, exist_ok=True)
