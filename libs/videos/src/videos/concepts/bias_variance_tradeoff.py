from __future__ import annotations

from videos.concepts._base import ConceptExtension
from videos.concepts._registry import ConceptRegistry
from videos.core.domain._concept import Concept, ConceptId, ConceptMetadata, ConceptTitle
from videos.core.domain._narrative import Beat, BeatKind, NarrationLine, Narrative


class BiasVarianceExtension(ConceptExtension):
    @property
    def concept(self) -> Concept:
        return Concept(
            id=ConceptId("bias_variance_tradeoff"),
            metadata=ConceptMetadata(
                title=ConceptTitle(
                    short="Bias-Variance Tradeoff",
                    subtitle="The fundamental tension in machine learning",
                ),
                description="Understanding the tradeoff between bias and variance in ML models",
                tags=("bias", "variance", "tradeoff", "statistics"),
            ),
        )

    def create_narrative(self) -> Narrative:
        return Narrative(
            self.concept,
            (
                Beat(
                    BeatKind.OPENING,
                    NarrationLine(
                        "Bias-Variance Tradeoff. "
                        "The fundamental tension in every machine learning model.",
                        6.0,
                    ),
                    "title",
                    {},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Imagine a dartboard. "
                        "The bullseye is the perfect prediction. "
                        "Every dart is a model prediction.",
                        7.0,
                    ),
                    "target",
                    {},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "High bias, low variance. "
                        "All darts cluster together, far from the bullseye. "
                        "The model is consistently wrong. "
                        "It has strong assumptions baked in.",
                        9.0,
                    ),
                    "high_bias",
                    {},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "What causes high bias? "
                        "An overly simple model. It assumes the data is linear "
                        "when the real relationship is curved. It underfits.",
                        7.0,
                    ),
                    "causes_bias",
                    {},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Low bias, high variance. "
                        "Darts spread all over. "
                        "On average they hit the center, but individual predictions "
                        "are all over the place. The model is too sensitive.",
                        9.0,
                    ),
                    "high_variance",
                    {},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "What causes high variance? "
                        "An overly complex model. It chases every data point "
                        "and memorizes noise instead of signal. It overfits.",
                        7.0,
                    ),
                    "causes_variance",
                    {},
                ),
                Beat(
                    BeatKind.EMPHASIS,
                    NarrationLine(
                        "Low bias, low variance. "
                        "Every dart hits the bullseye. "
                        "This is the sweet spot, and it is very hard to achieve.",
                        7.0,
                    ),
                    "sweet_spot",
                    {},
                ),
                Beat(
                    BeatKind.TRANSITION,
                    NarrationLine(
                        "The tradeoff is everywhere in machine learning. "
                        "Bias dominates when models are too simple. "
                        "Variance dominates when models are too complex.",
                        7.0,
                    ),
                    "graph",
                    {},
                ),
                Beat(
                    BeatKind.RECAP,
                    NarrationLine(
                        "Bias is wrong assumptions built into the model. "
                        "Variance is sensitivity to small fluctuations in training data. "
                        "Find the balance.",
                        8.0,
                    ),
                    "recap",
                    {},
                ),
            ),
        )


ConceptRegistry.register(BiasVarianceExtension())
