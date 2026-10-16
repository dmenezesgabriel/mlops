"""Pure text-fitting helpers for social-card composition.

Wrap, ellipsis, two-line rebalance, and size-from-box math are ported from
mkdocs-material's social plugin (research_repos/mkdocs-material/src/
plugins/social/plugin.py `_render_typography`/`_metrics`) with the font
measurements injected, so the geometry is testable without a rasterizer.
"""

from collections.abc import Callable
from statistics import stdev

# Pixels a string occupies on the canvas at the current font.
Measure = Callable[[str], float]

# (ascender, descender) of a font probed at a given pixel size.
Metrics = Callable[[int], tuple[int, int]]


def wrap_lines(
    text: str, measure: Measure, max_width: float, max_lines: int
) -> tuple[str, ...]:
    """Pack words into at most `max_lines` lines, ellipsizing overflow."""
    words = text.split()
    if not words:
        return ()
    space = measure(" ")
    lengths = [measure(word) for word in words]
    indexes = _line_break_indexes(lengths, space, max_width)
    if len(lengths) != indexes[-1]:
        indexes.append(len(lengths))
    indexes = _cap_lines(
        indexes, words, lengths, measure("..."), space, max_width, max_lines
    )
    return tuple(
        " ".join(words[start:end])
        # adjacent start/end pairs: indexes[1:] is shorter by design
        for start, end in zip(indexes, indexes[1:], strict=False)
    )


def _line_break_indexes(
    lengths: list[float], space: float, max_width: float
) -> list[int]:
    indexes, current = [0], 0.0
    for index, length in enumerate(lengths):
        whitespace = space if current else 0.0
        if current + whitespace + length > max_width and index != indexes[-1]:
            indexes.append(index)
            current = length
            continue
        current += whitespace + length
    return indexes


def _cap_lines(
    indexes: list[int],
    words: list[str],
    lengths: list[float],
    ellipsis: float,
    space: float,
    max_width: float,
    max_lines: int,
) -> list[int]:
    if max_lines < len(indexes) - 1:
        return _truncate_lines(
            indexes, words, lengths, ellipsis, space, max_width, max_lines
        )
    if len(indexes) == 3:
        return _rebalance_last_line(indexes, words)
    return indexes


def _truncate_lines(
    indexes: list[int],
    words: list[str],
    lengths: list[float],
    ellipsis: float,
    space: float,
    max_width: float,
    max_lines: int,
) -> list[int]:
    indexes = indexes[: max_lines + 1]
    start, end = indexes[-2:]
    last_width = sum(lengths[start:end]) + (end - start) * space
    if last_width + ellipsis < max_width:
        end += 1
    indexes[-1] = end
    words[end - 1] = "..."
    return indexes


def _rebalance_last_line(indexes: list[int], words: list[str]) -> list[int]:
    p, q, r = indexes[-3:]
    current = [len(" ".join(span)) for span in (words[p:q], words[q:r])]
    moved = [
        len(" ".join(span)) for span in (words[p : q - 1], words[q - 1 : r])
    ]
    if stdev(moved) < stdev(current):
        indexes[-2] -= 1
    return indexes


def fit_font_size(
    metrics: Metrics, box_height: int, max_lines: int, line_height: float
) -> tuple[int, float]:
    """Font size + spacing that fills `box_height` at `max_lines`.

    `metrics(size_px)` probes (ascender, descender); a 1000px probe keeps
    the division exact. Example::

        size, spacing = fit_font_size(font_at_size_metrics, 330, 3, 1.15)
    """
    ascender, descender = metrics(1000)
    extent = max_lines * ascender + descender
    extent += (max_lines - 1) * (line_height - 1) * ascender
    size = (1000 * box_height) / extent
    spacing = (line_height - 1) * ascender * size / 1000
    return int(size), spacing
