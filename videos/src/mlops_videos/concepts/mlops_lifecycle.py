from __future__ import annotations

from mlops_videos.adapters._manim._flow_builder import FlowBuilder
from mlops_videos.adapters._manim._scene import ConceptScene
from mlops_videos.concepts._base import ConceptExtension
from mlops_videos.concepts._registry import ConceptRegistry
from mlops_videos.core._domain._concept import Concept, ConceptId, ConceptMetadata, ConceptTitle
from mlops_videos.core._domain._narrative import Beat, BeatKind, NarrationLine, Narrative


class MlopsLifecycleExtension(ConceptExtension):
    @property
    def concept(self) -> Concept:
        return Concept(
            id=ConceptId("mlops_lifecycle"),
            metadata=ConceptMetadata(
                title=ConceptTitle(
                    short="MLOps Lifecycle",
                    subtitle="From data to production and back",
                ),
                description="Continuous Delivery for Machine Learning lifecycle based on CD4ML",
                tags=("mlops", "lifecycle", "cd4ml", "ml engineering"),
            ),
        )

    def create_narrative(self) -> Narrative:
        return Narrative(
            self.concept,
            (
                Beat(
                    BeatKind.OPENING,
                    NarrationLine(
                        "MLOps Lifecycle. Building a model is just the beginning. \
The real challenge is keeping it running and improving it.",
                        6.0,
                    ),
                    "title",
                    {},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Machine learning changes on 3 axes. Code, Data, and Model. \
Traditional DevOps only handles one of these.",
                        6.0,
                    ),
                    "three_axes",
                    {},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Data Collection. Version your data like you version your code. \
Without provenance, you cannot reproduce anything.",
                        5.0,
                    ),
                    "phase_collect",
                    {"color": "#4A90D9", "label": "Collect"},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Feature Engineering. Turn raw data into signals. \
Store features for reuse between training and serving.",
                        5.0,
                    ),
                    "phase_features",
                    {"color": "#50C878", "label": "Features"},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Training. Track every experiment. \
What parameters? What data? What metrics? \
If you didn't log it, it didn't happen.",
                        6.0,
                    ),
                    "phase_train",
                    {"color": "#FF8C42", "label": "Train"},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Model Registration. Not every model makes it. \
Promote the good ones, archive the rest. \
Governance matters.",
                        5.0,
                    ),
                    "phase_register",
                    {"color": "#9B59B6", "label": "Register"},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Deployment. Ship safely. Canary releases, blue-green deployments. \
Your model deserves the same care as any software.",
                        6.0,
                    ),
                    "phase_deploy",
                    {"color": "#E74C3C", "label": "Deploy"},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Monitoring. Watch for data drift, concept drift, \
performance degradation. Your model degrades over time.",
                        6.0,
                    ),
                    "phase_monitor",
                    {"color": "#00B5B8", "label": "Monitor"},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Why dedicate a whole practice to this? Because ML \
breaks in production. Data pipelines fail. Models drift. \
Without MLOps, you are flying blind.",
                        7.0,
                    ),
                    "why_mlops",
                    {},
                ),
                Beat(
                    BeatKind.EMPHASIS,
                    NarrationLine(
                        "BAM! The feedback loop. \
Production data feeds back into training. \
Your next model learns from the last one's mistakes.",
                        7.0,
                    ),
                    "feedback",
                    {},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Continuous improvement. Your model generates predictions. \
Those predictions become labeled data through monitoring. \
That data trains the next version. The loop never stops.",
                        6.0,
                    ),
                    "continuous",
                    {},
                ),
                Beat(
                    BeatKind.RECAP,
                    NarrationLine(
                        "Data to production and back. \
That is the MLOps lifecycle.",
                        4.0,
                    ),
                    "recap",
                    {},
                ),
            ),
        )


_PHASE_LABELS = ("Collect", "Features", "Train", "Register", "Deploy", "Monitor")
_PHASE_COLORS = ("#4A90D9", "#50C878", "#FF8C42", "#9B59B6", "#E74C3C", "#00B5B8")


class MlopsLifecycleScene(ConceptScene):
    concept_id = "mlops_lifecycle"

    def _on_opening_title(self, _beat: Beat) -> None:
        from manim import DOWN, UP, Text, VGroup, Write

        title = Text("MLOps Lifecycle", font_size=40)
        subtitle = Text("From data to production and back", font_size=22)
        subtitle.next_to(title, DOWN)
        group = VGroup(title, subtitle).to_edge(UP)
        self.play(Write(group))
        self._state["title_group"] = group

    def _on_reveal_three_axes(self, beat: Beat) -> None:
        from manim import Circle, Create, FadeIn, Text, VGroup

        circles = VGroup()
        items = (("Code", "#4A90D9"), ("Data", "#50C878"), ("Model", "#E74C3C"))
        for index, (label, color) in enumerate(items):
            circle = Circle(radius=0.8, color=color, fill_opacity=0.15)
            circle.shift([2.0 * (index - 1), 0, 0])
            text = Text(label, font_size=20).move_to(circle.get_center())
            group = VGroup(circle, text)
            circles.add(group)
            self.play(Create(group), run_time=0.5)

        label = Text("3 axes of change", font_size=18, color="#FFD700")
        label.shift([0, -1.5, 0])
        self.play(FadeIn(label))
        self._state["three_axes"] = VGroup(circles, label)
        self.wait(beat.narration.duration_seconds * 0.25)

    def _on_reveal_phase_collect(self, beat: Beat) -> None:
        self._reveal_phase(beat, 0)

    def _on_reveal_phase_features(self, beat: Beat) -> None:
        self._reveal_phase(beat, 1)

    def _on_reveal_phase_train(self, beat: Beat) -> None:
        self._reveal_phase(beat, 2)

    def _on_reveal_phase_register(self, beat: Beat) -> None:
        self._reveal_phase(beat, 3)

    def _on_reveal_phase_deploy(self, beat: Beat) -> None:
        self._reveal_phase(beat, 4)

    def _on_reveal_phase_monitor(self, beat: Beat) -> None:
        self._reveal_phase(beat, 5)

    def _reveal_phase(self, beat: Beat, index: int) -> None:
        import numpy as np
        from manim import FadeIn, Text

        label = Text(beat.params["label"], font_size=26, color=beat.params["color"])
        label.shift([-5.0 + 2.0 * index, 0, 0])
        self.play(FadeIn(label, shift=np.array([0, 0.5, 0])))
        self.wait(beat.narration.duration_seconds * 0.25)
        self._state[f"phase_{index}"] = label

    def _on_reveal_why_mlops(self, beat: Beat) -> None:
        from manim import Text, Write

        self._transition_to({})

        note = Text(
            "ML breaks in production without process",
            font_size=22,
            color="#FFD700",
        )
        self.play(Write(note))
        self._state["why_mlops_note"] = note
        self.wait(beat.narration.duration_seconds * 0.25)

    def _on_emphasis_feedback(self, beat: Beat) -> None:
        from manim import Create

        self._clear_state("why_mlops_note")
        self._clear_state(*[f"phase_{i}" for i in range(6)])
        self._clear_state("three_axes")

        cycle = FlowBuilder.build_cycle(self, _PHASE_LABELS, _PHASE_COLORS)
        arrows = FlowBuilder.add_cycle_arrows(self, cycle, color="#FFD700")
        self.play(Create(cycle), Create(arrows))
        self._state["cycle"] = cycle
        self._state["cycle_arrows"] = arrows

    def _on_reveal_continuous(self, beat: Beat) -> None:
        from manim import Text, Write

        self._transition_to({})

        note = Text(
            "Predictions \u2192 Monitor \u2192 Retrain \u2192 Improve",
            font_size=22,
            color="#50C878",
        )
        self.play(Write(note))
        self._state["continuous_note"] = note
        self.wait(beat.narration.duration_seconds * 0.25)

    def _on_recap_recap(self, beat: Beat) -> None:
        from manim import DOWN, Text, VGroup, Write

        self._transition_to({})

        summary = Text(
            "Collect \u2192 Features \u2192 Train \u2192 Register \u2192 Deploy \u2192 Monitor",
            font_size=24,
        )
        note = Text(
            "Production data feeds back into better models",
            font_size=18,
            color="#FFD700",
        )
        note.next_to(summary, DOWN)
        others = VGroup(summary, note)
        self.play(Write(others))
        self._state["recap"] = others


ConceptRegistry.register(MlopsLifecycleExtension())
