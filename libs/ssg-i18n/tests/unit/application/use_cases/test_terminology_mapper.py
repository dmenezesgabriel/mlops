from ssg_i18n.application.use_cases.terminology_mapper import TerminologyMapper
from ssg_i18n.domain.value_objects.locale import Locale

PT_BR = Locale("pt-BR")


class TestTerminologyMapper:
    def test_maps_alias_to_tag(self) -> None:
        mapper = TerminologyMapper()
        result = mapper.map_text("alias @my-model", PT_BR)
        assert "tag" in result

    def test_maps_batch_noun(self) -> None:
        mapper = TerminologyMapper()
        result = mapper.map_text("Batch Prediction", PT_BR)
        assert "em Batch" in result

    def test_replaces_deploy_with_implantacao(self) -> None:
        mapper = TerminologyMapper()
        result = mapper.map_text("deploy", PT_BR)
        assert result == "implantação"

    def test_no_mutation_on_clean_text(self) -> None:
        mapper = TerminologyMapper()
        result = mapper.map_text("pipeline", PT_BR)
        assert result == "pipeline"

    def test_rules_do_not_apply_to_non_pt_br_locales(self) -> None:
        mapper = TerminologyMapper()
        assert (
            mapper.map_text("Batch Verarbeitung ist fertig", Locale("de"))
            == "Batch Verarbeitung ist fertig"
        )
        assert mapper.map_text("deploy", Locale("en")) == "deploy"
        assert mapper.map_text("Batch Inferência", Locale("fr")) == (
            "Batch Inferência"
        )
