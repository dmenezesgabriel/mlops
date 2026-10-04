import typing
from typing import Self

import pytest
from videos.domain._base import PydanticModel
from videos.domain.concept import Concept
from videos.domain.concept_extension import ConceptExtension


class TestConceptExtension:
    def test_extension_is_abstract(self) -> None:
        assert ConceptExtension.__abstractmethods__ != frozenset()


class TestFromDict:
    def test_return_annotation_is_self(self) -> None:
        hints = typing.get_type_hints(PydanticModel.from_dict)
        assert hints["return"] is Self

    def test_returns_concept_instance(self) -> None:
        data = {
            "id": {"value": "mlops"},
            "metadata": {
                "title": {"short": "T", "subtitle": ""},
                "description": "",
                "tags": [],
            },
        }
        assert isinstance(Concept.from_dict(data), Concept)

    def test_rejects_malformed_data(self) -> None:
        with pytest.raises(ValueError):
            Concept.from_dict({"id": "not-a-mapping"})
