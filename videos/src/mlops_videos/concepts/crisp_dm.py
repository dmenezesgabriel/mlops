from __future__ import annotations

import numpy as np

from mlops_videos.adapters._manim._flow_builder import FlowBuilder
from mlops_videos.adapters._manim._scene import ConceptScene
from mlops_videos.concepts._base import ConceptExtension
from mlops_videos.concepts._registry import ConceptRegistry
from mlops_videos.core._domain._concept import Concept, ConceptId, ConceptMetadata, ConceptTitle
from mlops_videos.core._domain._narrative import Beat, BeatKind, NarrationLine, Narrative


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
                        "CRISP-DM. The most widely-used process for data mining projects. \
It stands for Cross-Industry Standard Process for Data Mining. \
Boring name, powerful framework.",
                        7.0,
                    ),
                    "title",
                    {},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Business Understanding. This is the most important step. \
Define the goal before touching any data.",
                        5.0,
                    ),
                    "phase_business",
                    {"color": "#4A90D9", "label": "Business\nUnderstanding"},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Data Understanding. What data do we have? Where does it live? \
Explore distributions, spot quality issues.",
                        5.0,
                    ),
                    "phase_data",
                    {"color": "#50C878", "label": "Data\nUnderstanding"},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Data Preparation. Cleaning, transforming, feature engineering. \
This takes 80 percent of the time.",
                        5.0,
                    ),
                    "phase_prepare",
                    {"color": "#00B5B8", "label": "Data\nPreparation"},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Modeling. Training candidate models, tuning parameters. \
Try different algorithms.",
                        5.0,
                    ),
                    "phase_model",
                    {"color": "#FF8C42", "label": "Modeling"},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Evaluation. Does the model solve the business problem? \
Not just accuracy — business value.",
                        5.0,
                    ),
                    "phase_evaluate",
                    {"color": "#9B59B6", "label": "Evaluation"},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Deployment. Put it in production. \
A model in a notebook does nobody any good. \
Ship it.",
                        5.0,
                    ),
                    "phase_deploy",
                    {"color": "#E74C3C", "label": "Deployment"},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Why a cycle? Because the real world keeps moving. \
Business priorities shift. New data arrives. \
Models degrade. CRISP-DM is designed for this.",
                        7.0,
                    ),
                    "why_iterative",
                    {},
                ),
                Beat(
                    BeatKind.EMPHASIS,
                    NarrationLine(
                        "BAM! It is not a one-way street. It is a cycle.",
                        5.0,
                    ),
                    "cycle",
                    {},
                ),
                Beat(
                    BeatKind.TRANSITION,
                    NarrationLine(
                        "You can always go back. Business changes? Go back. \
New data? Go back. Model not good enough? Go back.",
                        7.0,
                    ),
                    "back_arrows",
                    {},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Example: a bank builds a fraud detection model. \
Deploys it. Six months later, fraud patterns shift. \
Back to Data Understanding — the loop in action.",
                        7.0,
                    ),
                    "example",
                    {},
                ),
                Beat(
                    BeatKind.RECAP,
                    NarrationLine(
                        "Business first. Deploy to learn. Iterate forever. \
That is CRISP-DM.",
                        5.0,
                    ),
                    "recap",
                    {},
                ),
            ),
        )


_COLORS = ("#4A90D9", "#50C878", "#00B5B8", "#FF8C42", "#9B59B6", "#E74C3C")
_PHASE_LABELS = (
    "Business\nUnderstanding",
    "Data\nUnderstanding",
    "Data\nPreparation",
    "Modeling",
    "Evaluation",
    "Deployment",
)


class CrispDmScene(ConceptScene):
    concept_id = "crisp_dm"

    def _on_opening_title(self, _beat: Beat) -> None:
        from manim import DOWN, UP, Text, VGroup, Write

        title = Text("CRISP-DM", font_size=40)
        subtitle = Text("A practical loop for data mining", font_size=22)
        subtitle.next_to(title, DOWN)
        group = VGroup(title, subtitle).to_edge(UP)
        self.play(Write(group))
        self._state["title_group"] = group

    def _on_reveal_phase_business(self, beat: Beat) -> None:
        self._reveal_phase(beat, 0)

    def _on_reveal_phase_data(self, beat: Beat) -> None:
        self._reveal_phase(beat, 1)

    def _on_reveal_phase_prepare(self, beat: Beat) -> None:
        self._reveal_phase(beat, 2)

    def _on_reveal_phase_model(self, beat: Beat) -> None:
        self._reveal_phase(beat, 3)

    def _on_reveal_phase_evaluate(self, beat: Beat) -> None:
        self._reveal_phase(beat, 4)

    def _on_reveal_phase_deploy(self, beat: Beat) -> None:
        self._reveal_phase(beat, 5)

    def _reveal_phase(self, beat: Beat, index: int) -> None:
        from manim import FadeIn, Text

        label = Text(beat.params["label"], font_size=26, color=beat.params["color"])
        label.shift([-5.0 + 2.0 * index, 0, 0])
        self.play(FadeIn(label, shift=np.array([0, 0.5, 0])))
        self.wait(beat.narration.duration_seconds * 0.25)
        self._state[f"phase_{index}"] = label

    def _on_reveal_why_iterative(self, beat: Beat) -> None:
        from manim import Text, Write

        note = Text(
            "Real world changes \u2192 CRISP-DM adapts",
            font_size=22,
            color="#FFD700",
        )
        note.shift([0, -1.5, 0])
        self.play(Write(note))
        self._state["why_iterative_note"] = note
        self.wait(beat.narration.duration_seconds * 0.25)

    def _on_emphasis_cycle(self, beat: Beat) -> None:
        from manim import Create

        self._clear_state("why_iterative_note")
        self._clear_state(*[f"phase_{i}" for i in range(6)])

        cycles = FlowBuilder.build_cycle(self, _PHASE_LABELS, _COLORS)
        arrows = FlowBuilder.add_cycle_arrows(self, cycles, color="#FFD700")
        self.play(Create(cycles), Create(arrows))
        self._state["cycle"] = cycles
        self._state["arrows"] = arrows

    def _on_transition_back_arrows(self, beat: Beat) -> None:
        from manim import Create

        cycle = self._state.get("cycle")
        if cycle is not None:
            back_arrows = FlowBuilder.add_back_arrows(self, cycle, color="#FF6B6B")
            self.play(Create(back_arrows))
            self._state["back_arrows"] = back_arrows

    def _on_reveal_example(self, beat: Beat) -> None:
        from manim import Text, Write

        self._transition_to({})

        note = Text(
            "Fraud detection: deploy \u2192 patterns shift \u2192 revisit data",
            font_size=22,
            color="#4A90D9",
        )
        note.shift([0, 1.5, 0])
        self.play(Write(note))
        self._state["example_note"] = note
        self.wait(beat.narration.duration_seconds * 0.25)

    def _on_recap_recap(self, beat: Beat) -> None:
        from manim import DOWN, Text, VGroup, Write

        self._transition_to({})

        summary = Text(
            "Business \u2192 Data \u2192 Prepare \u2192 Model \u2192 Evaluate \u2192 Deploy",
            font_size=24,
        )
        note = Text("It is a cycle, not a waterfall", font_size=18, color="#FFD700")
        note.next_to(summary, DOWN)
        others = VGroup(summary, note)
        self.play(Write(others))
        self._state["recap"] = others


ConceptRegistry.register(CrispDmExtension())
