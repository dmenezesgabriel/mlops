from __future__ import annotations

from videos.concepts.base import ConceptExtension
from videos.core.domain.concept import Concept, ConceptId, ConceptMetadata, ConceptTitle
from videos.core.domain.narrative import Beat, BeatKind, NarrationLine, Narrative


class CrispDmExtension(ConceptExtension):
    @property
    def concept(self) -> Concept:
        return Concept(
            id=ConceptId("crisp_dm"),
            metadata=ConceptMetadata(
                title=ConceptTitle(
                    short="CRISP-DM",
                    subtitle="A practical loop for data mining projects",
                ),
                description="Cross-Industry Standard Process for Data Mining",
                tags=("data mining", "methodology", "process"),
            ),
        )

    def create_narrative(self) -> Narrative:
        return Narrative(
            self.concept,
            (
                Beat(
                    BeatKind.OPENING,
                    NarrationLine(
                        "CRISP-DM. The most widely-used process for data mining projects. "
                        "Boring name, powerful framework.",
                        7.0,
                    ),
                    "title",
                    {},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Business Understanding. Define the goal before touching any data.",
                        5.0,
                    ),
                    "phase_business",
                    {"color": "#4A90D9", "label": "Business\nUnderstanding"},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Data Understanding. Explore distributions, spot quality issues.",
                        5.0,
                    ),
                    "phase_data",
                    {"color": "#50C878", "label": "Data\nUnderstanding"},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Data Preparation. Cleaning, transforming, feature engineering. "
                        "This takes 80 percent of the time.",
                        5.0,
                    ),
                    "phase_prepare",
                    {"color": "#00B5B8", "label": "Data\nPreparation"},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Modeling. Training candidate models, tuning parameters.",
                        5.0,
                    ),
                    "phase_model",
                    {"color": "#FF8C42", "label": "Modeling"},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Evaluation. Does the model solve the business problem? "
                        "Not just accuracy — business value.",
                        5.0,
                    ),
                    "phase_evaluate",
                    {"color": "#9B59B6", "label": "Evaluation"},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Deployment. A model in a notebook does nobody any good. Ship it.",
                        5.0,
                    ),
                    "phase_deploy",
                    {"color": "#E74C3C", "label": "Deployment"},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Why a cycle? Business priorities shift. "
                        "New data arrives. Models degrade. "
                        "CRISP-DM is designed for this.",
                        7.0,
                    ),
                    "why_iterative",
                    {},
                ),
                Beat(
                    BeatKind.EMPHASIS,
                    NarrationLine(
                        "It is not a one-way street. It is a cycle.",
                        5.0,
                    ),
                    "cycle",
                    {},
                ),
                Beat(
                    BeatKind.TRANSITION,
                    NarrationLine(
                        "You can always go back. Business changes? Go back. New data? Go back.",
                        7.0,
                    ),
                    "back_arrows",
                    {},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Example: fraud detection. "
                        "Deploy. Six months later patterns shift. "
                        "Back to Data Understanding — the loop in action.",
                        7.0,
                    ),
                    "example",
                    {},
                ),
                Beat(
                    BeatKind.RECAP,
                    NarrationLine(
                        "Business first. Deploy to learn. Iterate forever. That is CRISP-DM.",
                        5.0,
                    ),
                    "recap",
                    {},
                ),
            ),
        )
