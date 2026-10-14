# files() is Python 3.9+; this package requires >= 3.11
# nosemgrep: python.lang.compatibility.python37.python37-compatibility-importlib2
from importlib.resources import files


def _read_frontend_asset(relative_path: str) -> str:
    asset_path = files("ssg.infrastructure.frontend").joinpath(
        "static", relative_path
    )
    if not asset_path.is_file():
        raise FileNotFoundError(
            f"Missing frontend asset {relative_path}: expected package file under "
            "ssg.infrastructure.frontend/static",
        )

    return asset_path.read_text(encoding="utf-8").strip()


SITE_CSS = _read_frontend_asset("css/site.css")
SITE_JS = _read_frontend_asset("js/site.js")
SITE_FAVICON = _read_frontend_asset("favicon.svg")

__all__ = ["SITE_CSS", "SITE_FAVICON", "SITE_JS"]
