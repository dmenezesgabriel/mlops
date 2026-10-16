import json
import shutil
from pathlib import Path
from typing import cast

from ssg.domain import Site, SiteVersion, SiteVersioning

# Root-level files the layout itself owns — kept across a prepare sweep
# because finalize rewrites them; everything else at the root of a
# versioned build is either a version dir or a stale unversioned-era
# leftover.
_ROOT_KEEP_FILES = frozenset(
    {"index.html", "404.html", "versions.json", ".nojekyll"}
)

_VERSIONS_JSON = "versions.json"


def emission_segments(site: Site) -> tuple[str, ...]:
    """Output segments the builder renders into — the current version id,
    or a single empty segment (the output root) when unversioned."""
    versioning = site.versioning
    if versioning is None:
        return ("",)
    return versioning.build_segments()


def prepare_versioned_output(
    output_path: Path, versioning: SiteVersioning
) -> None:
    """Sweep the build root for a versioned emit: drop unversioned-era
    leftovers, clear the dirs this build re-emits (current + its aliases),
    keep every other declared or previously-deployed version dir."""
    if not output_path.is_dir():
        return
    kept = _kept_root_names(output_path, versioning)
    for child in output_path.iterdir():
        if child.name in kept:
            continue
        if child.is_symlink() or not child.is_dir():
            child.unlink()
        else:
            shutil.rmtree(child)
    for segment in versioning.output_segments():
        shutil.rmtree(output_path / segment, ignore_errors=True)


def finalize_versioned_output(
    output_path: Path, versioning: SiteVersioning, redirect_html: str
) -> None:
    """Finish the versioned layout: copy the freshly-built current tree
    into each alias dir (mike's copy alias-type — canonicals inside stay
    on the real version), rewrite versions.json merged with whatever the
    previous artifact knew, and lay down the root redirect + 404."""
    current_dir = output_path / versioning.current
    if not current_dir.is_dir():
        raise ValueError(
            f"versioned output is missing the current version dir "
            f"{current_dir}; expected the builder to emit it before finalize"
        )
    for segment in versioning.output_segments()[1:]:
        shutil.copytree(current_dir, output_path / segment, dirs_exist_ok=True)
    merged = merge_version_entries(read_versions_json(output_path), versioning)
    _write_versions_json(output_path, _present_entries(output_path, merged))
    (output_path / "index.html").write_text(redirect_html, encoding="utf-8")
    default_404 = output_path / versioning.default_version_id() / "404.html"
    if default_404.is_file():
        shutil.copyfile(default_404, output_path / "404.html")


def _kept_root_names(
    output_path: Path, versioning: SiteVersioning
) -> set[str]:
    merged = merge_version_entries(read_versions_json(output_path), versioning)
    kept = {entry.id for entry in merged}
    for entry in merged:
        kept.update(entry.aliases)
    return kept | _ROOT_KEEP_FILES


def merge_version_entries(
    existing: tuple[SiteVersion, ...], versioning: SiteVersioning
) -> tuple[SiteVersion, ...]:
    """Config-declared versions first, then entries only the previous
    artifact knew — an old checkout rebuilding an old version must not
    unlist a newer deployed one."""
    merged = list(versioning.versions)
    for entry in existing:
        if versioning.entry_for(entry.id) is None:
            merged.append(entry)
    return tuple(merged)


def read_versions_json(output_path: Path) -> tuple[SiteVersion, ...]:
    """Best-effort read of the previous artifact's registry; a missing or
    malformed file just means 'nothing deployed yet'."""
    path = output_path / _VERSIONS_JSON
    if not path.is_file():
        return ()
    try:
        payload: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    if not isinstance(payload, list):
        return ()
    items = cast(list[object], payload)
    return tuple(
        entry for entry in (_parse_json_entry(item) for item in items) if entry
    )


def _parse_json_entry(item: object) -> SiteVersion | None:
    if not isinstance(item, dict):
        return None
    entry = cast(dict[object, object], item)
    version = entry.get("version")
    if not isinstance(version, str) or not version:
        return None
    title = entry.get("title")
    aliases = entry.get("aliases")
    properties = entry.get("properties")
    return SiteVersion(
        id=version,
        title=title if isinstance(title, str) and title else version,
        aliases=(
            tuple(
                alias
                for alias in cast(list[object], aliases)
                if isinstance(alias, str)
            )
            if isinstance(aliases, list)
            else ()
        ),
        hidden=(
            isinstance(properties, dict)
            and bool(cast(dict[object, object], properties).get("hidden"))
        ),
    )


def _present_entries(
    output_path: Path, entries: tuple[SiteVersion, ...]
) -> tuple[SiteVersion, ...]:
    """Drop registry entries whose dir never landed — the switcher must
    not link ghosts."""
    return tuple(e for e in entries if (output_path / e.id).is_dir())


def _write_versions_json(
    output_path: Path, entries: tuple[SiteVersion, ...]
) -> None:
    payload = [_json_entry(entry) for entry in entries]
    (output_path / _VERSIONS_JSON).write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )


def _json_entry(entry: SiteVersion) -> dict[str, object]:
    payload: dict[str, object] = {
        "version": entry.id,
        "title": entry.title,
        "aliases": list(entry.aliases),
    }
    if entry.hidden:
        payload["properties"] = {"hidden": True}
    return payload
