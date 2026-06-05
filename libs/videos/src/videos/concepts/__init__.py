from __future__ import annotations

from videos.concepts.registry import ConceptRegistry


def register_all() -> None:
    from videos.concepts.bias_variance_tradeoff import BiasVarianceExtension
    from videos.concepts.crisp_dm import CrispDmExtension
    from videos.concepts.mlops_lifecycle import MlopsLifecycleExtension
    from videos.concepts.underfit_vs_overfit import UnderfitOverfitExtension

    ConceptRegistry.register(BiasVarianceExtension())
    ConceptRegistry.register(CrispDmExtension())
    ConceptRegistry.register(MlopsLifecycleExtension())
    ConceptRegistry.register(UnderfitOverfitExtension())
