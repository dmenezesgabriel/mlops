from __future__ import annotations

from videos.concepts._base import ConceptExtension
from videos.concepts._registry import ConceptRegistry
from videos.core.domain._concept import Concept, ConceptId, ConceptMetadata, ConceptTitle
from videos.core.domain._narrative import Beat, BeatKind, NarrationLine, Narrative


class UnderfitOverfitExtension(ConceptExtension):
    @property
    def concept(self) -> Concept:
        return Concept(
            id=ConceptId("underfit_vs_overfit"),
            metadata=ConceptMetadata(
                title=ConceptTitle(
                    short="Underfitting vs Overfitting",
                    subtitle="Too simple or too complex",
                ),
                description="When a model is too simple or too complex for the data",
                tags=("underfitting", "overfitting", "bias", "variance"),
            ),
        )

    def create_narrative(self) -> Narrative:
        return Narrative(
            self.concept,
            (
                Beat(
                    BeatKind.OPENING,
                    NarrationLine(
                        "Underfitting vs Overfitting. Too simple or too complex.",
                        5.0,
                    ),
                    "title",
                    {},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Points that follow a clear pattern with some noise mixed in. "
                        "A good model captures the pattern, not the noise.",
                        7.0,
                    ),
                    "data_points",
                    {},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Underfitting. The model is too simple. "
                        "A straight line through curved data. "
                        "It misses the pattern entirely.",
                        9.0,
                    ),
                    "underfit",
                    {},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Overfitting. The model is too complex. "
                        "It memorizes every data point including the noise. "
                        "Zero training error but terrible validation error.",
                        9.0,
                    ),
                    "overfit",
                    {},
                ),
                Beat(
                    BeatKind.EMPHASIS,
                    NarrationLine(
                        "Just right. Captures the underlying pattern without noise. "
                        "Good training error AND good validation error.",
                        7.0,
                    ),
                    "just_right",
                    {},
                ),
                Beat(
                    BeatKind.TRANSITION,
                    NarrationLine(
                        "Both high errors = underfit. Low training + high validation = overfit.",
                        7.0,
                    ),
                    "diagnosis",
                    {},
                ),
                Beat(
                    BeatKind.TRANSITION,
                    NarrationLine(
                        "Fix overfitting with regularization. "
                        "Fix underfitting with more features or a bigger model.",
                        7.0,
                    ),
                    "fixes",
                    {},
                ),
                Beat(
                    BeatKind.RECAP,
                    NarrationLine(
                        "Underfit needs more model capacity. "
                        "Overfit needs more data or regularization. "
                        "Your validation set tells you which.",
                        8.0,
                    ),
                    "recap",
                    {},
                ),
            ),
        )


ConceptRegistry.register(UnderfitOverfitExtension())
