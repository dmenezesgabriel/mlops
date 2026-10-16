from hashlib import sha256
from pathlib import Path

from ssg.domain import PrecacheManifest


def precache_manifest(
    output_path: Path, nested_output_paths: tuple[Path, ...]
) -> PrecacheManifest:
    """Compute the emitted tree's precache manifest for a site variant.

    The manifest walks the output directory — the same tree a static host
    serves — rather than the page model, so it stays correct across
    incremental rebuilds that leave earlier pages on disk. Example:

        >>> precache_manifest(Path("site/build"), (Path("site/build/pt-BR"),))

    """
    paths = sorted(
        path
        for path in output_path.rglob("*")
        if _is_precacheable(output_path, path, nested_output_paths)
    )
    urls, version = _manifest_entries(output_path, paths)
    return PrecacheManifest(urls=("./", *urls), version=version)


def _is_precacheable(
    output_path: Path, path: Path, nested_output_paths: tuple[Path, ...]
) -> bool:
    if not path.is_file() or path.name == "sw.js":
        return False
    if any(path.is_relative_to(nested) for nested in nested_output_paths):
        # A non-default locale output nests inside the default root; each
        # variant precaches only its own tree.
        return False
    # embed_video output is the only unbounded-size artifact; a quota
    # rejection in cache.addAll aborts the worker install, so videos fall
    # back to network-only. assets/social/ holds crawler-only og:image
    # cards — precaching them would inflate the install set a browser
    # never fetches.
    parent = path.relative_to(output_path).parent.as_posix()
    return "assets/videos" not in parent and "assets/social" not in parent


def _manifest_entries(
    output_path: Path, paths: list[Path]
) -> tuple[tuple[str, ...], str]:
    digest = sha256()
    urls: list[str] = []
    for path in paths:
        relative = path.relative_to(output_path).as_posix()
        urls.append(relative)
        digest.update(relative.encode())
        digest.update(sha256(path.read_bytes()).hexdigest().encode())
    return tuple(urls), digest.hexdigest()[:16]
