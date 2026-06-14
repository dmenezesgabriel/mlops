from ssg_i18n_machine_translation.domain.value_objects.line_result import (
    LineResult,
)


class TestLineResult:
    def test_is_fallback_field(self) -> None:
        result = LineResult(
            is_fallback=True, is_wiki_mismatch=False, is_table_mismatch=False
        )
        assert result.is_fallback is True

    def test_is_wiki_mismatch_field(self) -> None:
        result = LineResult(
            is_fallback=False, is_wiki_mismatch=True, is_table_mismatch=False
        )
        assert result.is_wiki_mismatch is True

    def test_is_table_mismatch_field(self) -> None:
        result = LineResult(
            is_fallback=False, is_wiki_mismatch=False, is_table_mismatch=True
        )
        assert result.is_table_mismatch is True

    def test_all_false_by_default_pattern(self) -> None:
        result = LineResult(
            is_fallback=False, is_wiki_mismatch=False, is_table_mismatch=False
        )
        assert not result.is_fallback
        assert not result.is_wiki_mismatch
        assert not result.is_table_mismatch
