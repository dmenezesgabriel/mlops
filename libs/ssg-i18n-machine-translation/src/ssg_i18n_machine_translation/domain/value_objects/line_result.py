from dataclasses import dataclass


@dataclass(frozen=True)
class LineResult:
    """Evaluation outcome for a single translated line pair.

    Example:
        LineResult(is_fallback=True, is_wiki_mismatch=False, is_table_mismatch=False)
    """

    is_fallback: bool
    is_wiki_mismatch: bool
    is_table_mismatch: bool
