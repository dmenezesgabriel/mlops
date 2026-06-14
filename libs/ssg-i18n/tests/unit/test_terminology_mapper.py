from ssg_i18n.application.terminology_mapper import TerminologyMapper


def test_map_batch_phrase() -> None:
    mapper = TerminologyMapper()
    # Batch Noun -> Noun em Batch
    assert mapper.map_text("Batch Inferência") == "Inferência em Batch"
    assert mapper.map_text("Batch predição") == "predição em Batch"
    assert mapper.map_text("Batch processamento") == "processamento em Batch"


def test_map_alias_phrase() -> None:
    mapper = TerminologyMapper()
    # O @champion Alias -> A Tag @champion
    assert mapper.map_text("O @champion Alias") == "A Tag @champion"
    assert mapper.map_text("o @champion alias") == "a tag @champion"
    assert mapper.map_text("champion alias") == "tag champion"
    assert mapper.map_text("Alias champion") == "tag champion"


def test_map_deploy_term() -> None:
    mapper = TerminologyMapper()
    assert mapper.map_text("Deploy") == "Implantação"
    assert mapper.map_text("deploy") == "implantação"
    assert mapper.map_text("implantar para") == "implantação para"


def test_map_gasoduto_term() -> None:
    mapper = TerminologyMapper()
    assert (
        mapper.map_text("O gasoduto de deploy") == "O pipeline de implantação"
    )
    assert mapper.map_text("gasodutos") == "pipelines"


def test_map_new_terminology_rules() -> None:
    mapper = TerminologyMapper()
    # Check that generic aliases are not modified incorrectly
    assert (
        mapper.map_text("usando um alias lógico") == "usando um alias lógico"
    )

    # Check that specific alias rules work with articles and prepositions
    assert mapper.map_text("o alias TR0") == "a tag TR0"
    assert mapper.map_text("um alias champion") == "uma tag champion"
    assert mapper.map_text("do alias @champion") == "da tag @champion"

    # Check new term replacements
    assert mapper.map_text("encanamento de dados") == "pipeline de dados"
    assert mapper.map_text("captadores de táxi") == "embarques de táxi"
    assert mapper.map_text("drift característica") == "drift de característica"
