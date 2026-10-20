"""Typed surface of joblib's persistence helpers used by the entrypoint."""

from os import PathLike

def dump(
    value: object,
    filename: str | PathLike[str],
    compress: int | tuple[int, int] = ...,
    protocol: int | None = ...,
    cache_size: int | None = ...,
) -> list[str]: ...
