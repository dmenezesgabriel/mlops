from dataclasses import dataclass


@dataclass(frozen=True)
class PrecacheManifest:
    # urls: scope-relative paths the service worker precaches ("./" covers
    # the variant root itself); version: content hash of the emitted tree,
    # so any output change mints a fresh cache name on the next deploy.
    urls: tuple[str, ...]
    version: str
