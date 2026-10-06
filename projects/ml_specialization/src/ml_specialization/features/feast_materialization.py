from pathlib import Path


class LocalFeastMaterializer:
    """Apply Feast definitions against the local registry and online store.

    Stub left for the specialization exercises — calls raise
    NotImplementedError.

    Example:
        LocalFeastMaterializer().apply(Path("feature_repo"))
    """

    def apply(self, repo_path: Path) -> None:
        raise NotImplementedError(
            "LocalFeastMaterializer.apply is not implemented"
        )
