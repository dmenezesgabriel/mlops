"""Step definitions for the engine versions BDD feature (MD-5).

ListEngineVersions needs no store; the step asserts the pinned single-entry
list matches the canonical ``EngineVersions``/``EngineVersion`` shapes.
"""

from __future__ import annotations

from athena_local.engine_versions import list_engine_versions
from pytest_bdd import parsers, scenarios, then, when

scenarios("engine_versions.feature")


@when("ListEngineVersions is called")
def _call_list_engine_versions() -> None:
    # The operation is stateless; assertions re-invoke it directly.
    pass


@then(parsers.parse("the response contains {num:d} engine version"))
def _response_has_one_engine_version(num: int) -> None:
    output = list_engine_versions(None)
    assert len(output["EngineVersions"]) == num


@then(
    parsers.parse(
        'the engine is "{selected}" with effective version "{effective}"'
    )
)
def _engine_values(selected: str, effective: str) -> None:
    output = list_engine_versions(None)
    assert output["EngineVersions"][0] == {
        "SelectedEngineVersion": selected,
        "EffectiveEngineVersion": effective,
    }


@then("no NextToken is returned")
def _no_next_token() -> None:
    assert "NextToken" not in list_engine_versions(None)
