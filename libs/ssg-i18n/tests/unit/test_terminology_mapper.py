from ssg_i18n.application.terminology_mapper import TerminologyMapper
from ssg_i18n.domain.locale import Locale

PT_BR = Locale("pt-BR")


def test_map_batch_phrase() -> None:
    mapper = TerminologyMapper()
    # Batch Noun -> Noun em Batch
    assert mapper.map_text("Batch Inferência", PT_BR) == "Inferência em Batch"
    assert mapper.map_text("Batch predição", PT_BR) == "predição em Batch"
    assert (
        mapper.map_text("Batch processamento", PT_BR)
        == "processamento em Batch"
    )


def test_map_alias_phrase() -> None:
    mapper = TerminologyMapper()
    # O @champion Alias -> A Tag @champion
    assert mapper.map_text("O @champion Alias", PT_BR) == "A Tag @champion"
    assert mapper.map_text("o @champion alias", PT_BR) == "a tag @champion"
    assert mapper.map_text("champion alias", PT_BR) == "tag champion"
    assert mapper.map_text("Alias champion", PT_BR) == "tag champion"


def test_map_deploy_term() -> None:
    mapper = TerminologyMapper()
    assert mapper.map_text("Deploy", PT_BR) == "Implantação"
    assert mapper.map_text("deploy", PT_BR) == "implantação"
    assert mapper.map_text("implantar para", PT_BR) == "implantação para"


def test_map_gasoduto_term() -> None:
    mapper = TerminologyMapper()
    assert (
        mapper.map_text("O gasoduto de deploy", PT_BR)
        == "O pipeline de implantação"
    )
    assert mapper.map_text("gasodutos", PT_BR) == "pipelines"


def test_map_new_terminology_rules() -> None:
    mapper = TerminologyMapper()
    # Check that generic aliases are not modified incorrectly
    assert (
        mapper.map_text("usando um alias lógico", PT_BR)
        == "usando um alias lógico"
    )

    # Check that specific alias rules work with articles and prepositions
    assert mapper.map_text("o alias TR0", PT_BR) == "a tag TR0"
    assert mapper.map_text("um alias champion", PT_BR) == "uma tag champion"
    assert mapper.map_text("do alias @champion", PT_BR) == "da tag @champion"

    # Check new term replacements
    assert (
        mapper.map_text("encanamento de dados", PT_BR) == "pipeline de dados"
    )
    assert mapper.map_text("captadores de táxi", PT_BR) == "embarques de táxi"
    assert (
        mapper.map_text("drift característica", PT_BR)
        == "drift de característica"
    )


def test_pt_br_rules_do_not_apply_to_other_locales() -> None:
    mapper = TerminologyMapper()
    assert (
        mapper.map_text("Batch Verarbeitung ist fertig", Locale("de"))
        == "Batch Verarbeitung ist fertig"
    )
    assert mapper.map_text("deploy", Locale("en")) == "deploy"
