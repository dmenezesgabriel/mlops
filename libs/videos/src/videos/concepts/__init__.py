from __future__ import annotations

from pathlib import Path

from videos.concepts.registry import ConceptRegistry
from videos.declarative.discovery import find_concept_yaml_files
from videos.declarative.loader import load_concept_from_yaml_file


def register_all() -> None:
    from videos.concepts.bias_variance_tradeoff import BiasVarianceExtension
    from videos.concepts.crisp_dm import CrispDmExtension
    from videos.concepts.mlops_lifecycle import MlopsLifecycleExtension
    from videos.concepts.underfit_vs_overfit import UnderfitOverfitExtension

    ConceptRegistry.register(BiasVarianceExtension())
    ConceptRegistry.register(CrispDmExtension())
    ConceptRegistry.register(MlopsLifecycleExtension())
    ConceptRegistry.register(UnderfitOverfitExtension())

    yaml_dir = Path(__file__).parent / "yaml"
    for yaml_path in find_concept_yaml_files(yaml_dir):
        ext = load_concept_from_yaml_file(str(yaml_path))
        ConceptRegistry.register(ext)
