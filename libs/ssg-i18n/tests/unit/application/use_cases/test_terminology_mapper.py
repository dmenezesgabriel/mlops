from ssg_i18n.application.use_cases.terminology_mapper import TerminologyMapper


class TestTerminologyMapper:
    def test_maps_alias_to_tag(self) -> None:
        mapper = TerminologyMapper()
        result = mapper.map_text("alias @my-model")
        assert "tag" in result

    def test_maps_batch_noun(self) -> None:
        mapper = TerminologyMapper()
        result = mapper.map_text("Batch Prediction")
        assert "em Batch" in result

    def test_replaces_deploy_with_implantacao(self) -> None:
        mapper = TerminologyMapper()
        result = mapper.map_text("deploy")
        assert result == "implantação"

    def test_no_mutation_on_clean_text(self) -> None:
        mapper = TerminologyMapper()
        result = mapper.map_text("pipeline")
        assert result == "pipeline"
