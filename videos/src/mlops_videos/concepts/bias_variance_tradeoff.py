from __future__ import annotations

import math

from mlops_videos.adapters._manim._scene import ConceptScene
from mlops_videos.adapters._manim._target_builder import TargetBuilder
from mlops_videos.concepts._base import ConceptExtension
from mlops_videos.concepts._registry import ConceptRegistry
from mlops_videos.core._domain._concept import Concept, ConceptId, ConceptMetadata, ConceptTitle
from mlops_videos.core._domain._narrative import Beat, BeatKind, NarrationLine, Narrative

_TARGET_CENTER = (-3.5, 0, 0)


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
                        "Bias-Variance Tradeoff. \
The fundamental tension in every machine learning model.",
                        6.0,
                    ),
                    "title",
                    {},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Imagine a dartboard. \
The bullseye is the perfect prediction. \
Every dart is a model prediction.",
                        7.0,
                    ),
                    "target",
                    {},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "High bias, low variance. \
All darts cluster together, far from the bullseye. \
The model is consistently wrong. \
It has strong assumptions baked in.",
                        9.0,
                    ),
                    "high_bias",
                    {},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "What causes high bias? \
An overly simple model. It assumes the data is linear \
when the real relationship is curved. It underfits.",
                        7.0,
                    ),
                    "causes_bias",
                    {},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Low bias, high variance. \
Darts spread all over. \
On average they hit the center, but individual predictions are all over the place. \
The model is too sensitive to training data.",
                        9.0,
                    ),
                    "high_variance",
                    {},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "What causes high variance? \
An overly complex model. It chases every data point \
and memorizes noise instead of signal. It overfits.",
                        7.0,
                    ),
                    "causes_variance",
                    {},
                ),
                Beat(
                    BeatKind.EMPHASIS,
                    NarrationLine(
                        "Low bias, low variance. \
Every dart hits the bullseye. \
This is the sweet spot, and it is very hard to achieve.",
                        7.0,
                    ),
                    "sweet_spot",
                    {},
                ),
                Beat(
                    BeatKind.TRANSITION,
                    NarrationLine(
                        "The tradeoff is everywhere in machine learning. \
Bias dominates when models are too simple. \
Variance dominates when models are too complex.",
                        7.0,
                    ),
                    "graph",
                    {},
                ),
                Beat(
                    BeatKind.RECAP,
                    NarrationLine(
                        "Bias is wrong assumptions built into the model. \
Variance is sensitivity to small fluctuations in training data. \
You trade one for the other. Find the balance.",
                        8.0,
                    ),
                    "recap",
                    {},
                ),
            ),
        )


class BiasVarianceTradeoffScene(ConceptScene):
    concept_id = "bias_variance_tradeoff"

    def _on_opening_title(self, _beat: Beat) -> None:
        from manim import DOWN, UP, Text, VGroup, Write

        title = Text("Bias-Variance Tradeoff", font_size=40)
        subtitle = Text("The fundamental tension in machine learning", font_size=22)
        subtitle.next_to(title, DOWN)
        group = VGroup(title, subtitle).to_edge(UP)
        self.play(Write(group))
        self._state["title_group"] = group

    def _on_reveal_target(self, beat: Beat) -> None:
        from manim import Create

        target = TargetBuilder.create_target(self, rings=4, max_radius=2.0)
        target.move_to(_TARGET_CENTER)
        self.play(Create(target))
        self._state["target"] = target
        self.wait(beat.narration.duration_seconds * 0.25)

    def _on_reveal_high_bias(self, beat: Beat) -> None:
        from manim import DOWN, Create, Text

        target = self._state.get("target")
        if target is None:
            return
        cx, cy, _ = _TARGET_CENTER
        positions = [
            (cx - 0.5, cy + 0.5),
            (cx - 0.3, cy + 0.7),
            (cx - 0.7, cy + 0.3),
            (cx - 0.4, cy + 0.6),
        ]
        darts = TargetBuilder.create_darts(self, positions, color="#E74C3C")
        self.play(Create(darts))
        label = Text("High Bias, Low Variance", font_size=18, color="#E74C3C")
        label.next_to(target, DOWN, buff=0.8)
        self.play(Create(label))
        self._state["high_bias_darts"] = darts
        self._state["high_bias_label"] = label
        self.wait(beat.narration.duration_seconds * 0.25)

    def _on_reveal_causes_bias(self, beat: Beat) -> None:
        from manim import DOWN, Text, Write

        note = Text(
            "Model too simple → misses the pattern",
            font_size=22,
            color="#E74C3C",
        )
        note.next_to(self._state.get("high_bias_label", self), DOWN, buff=0.4)
        self.play(Write(note))
        self._state["causes_bias_note"] = note
        self.wait(beat.narration.duration_seconds * 0.25)

    def _on_reveal_high_variance(self, beat: Beat) -> None:
        from manim import DOWN, Create, Text

        self._clear_state("high_bias_darts", "high_bias_label", "causes_bias_note")

        target = self._state.get("target")
        if target is None:
            return
        cx, cy, _ = _TARGET_CENTER
        positions = [
            (cx - 1.0, cy + 1.2),
            (cx + 0.5, cy + 0.8),
            (cx - 1.3, cy - 0.5),
            (cx + 1.0, cy - 0.3),
            (cx - 0.3, cy - 1.0),
            (cx + 0.6, cy + 0.0),
        ]
        darts = TargetBuilder.create_darts(self, positions, color="#FF8C42")
        self.play(Create(darts))
        label = Text("Low Bias, High Variance", font_size=18, color="#FF8C42")
        label.next_to(target, DOWN, buff=0.8)
        self.play(Create(label))
        self._state["high_var_darts"] = darts
        self._state["high_var_label"] = label
        self.wait(beat.narration.duration_seconds * 0.25)

    def _on_reveal_causes_variance(self, beat: Beat) -> None:
        from manim import DOWN, Text, Write

        note = Text(
            "Model too complex → chases noise",
            font_size=22,
            color="#FF8C42",
        )
        note.next_to(self._state.get("high_var_label", self), DOWN, buff=0.4)
        self.play(Write(note))
        self._state["causes_var_note"] = note
        self.wait(beat.narration.duration_seconds * 0.25)

    def _on_emphasis_sweet_spot(self, beat: Beat) -> None:
        from manim import DOWN, Create, Text

        self._clear_state("high_var_darts", "high_var_label", "causes_var_note")

        target = self._state.get("target")
        if target is None:
            return
        cx, cy, _ = _TARGET_CENTER
        positions = [(cx, cy), (cx + 0.1, cy + 0.1), (cx - 0.1, cy - 0.1), (cx + 0.1, cy)]
        darts = TargetBuilder.create_darts(self, positions, color="#00FF00")
        self.play(Create(darts))
        label = Text("Low Bias, Low Variance  (sweet spot)", font_size=20, color="#00FF00")
        label.next_to(target, DOWN, buff=0.8)
        self.play(Create(label))
        self._state["sweet_darts"] = darts
        self._state["sweet_label"] = label
        self.wait(beat.narration.duration_seconds * 0.25)

    def _on_transition_graph(self, beat: Beat) -> None:
        from manim import DOWN, UP, Create, Text, VGroup

        from mlops_videos.adapters._manim._graph_builder import GraphBuilder

        self._transition_to({})

        axes = GraphBuilder.create_axes(
            self,
            x_range=(0, 10, 1),
            y_range=(0, 5, 1),
        )
        axes.shift([2, 0, 0]).scale(0.7)
        self.play(Create(axes))

        def val_curve(x: float) -> float:
            return 0.05 * (x - 5) ** 2 + 0.5

        def train_curve(x: float) -> float:
            return 5.0 * math.exp(-0.3 * x) + 0.5

        val_plot = axes.plot(val_curve, x_range=(0, 10), color="#E74C3C")
        train_plot = axes.plot(train_curve, x_range=(0, 10), color="#50C878")
        self.play(Create(val_plot), Create(train_plot))

        bias_label = Text("Bias dominates", font_size=16, color="#4A90D9")
        bias_label.next_to(axes.c2p(1.5, 2.5), UP, buff=0.1)
        var_label = Text("Variance dominates", font_size=16, color="#E74C3C")
        var_label.next_to(axes.c2p(8.5, 2.5), UP, buff=0.1)
        sweet_label = Text("Sweet spot", font_size=16, color="#FFD700")
        sweet_label.next_to(axes.c2p(5, 0.5), DOWN, buff=0.1)
        labels = VGroup(bias_label, var_label, sweet_label)
        self.play(Create(labels))

        self._state.update(
            {
                "axes": axes,
                "val_plot": val_plot,
                "train_plot": train_plot,
                "graph_labels": labels,
            }
        )

    def _on_recap_recap(self, beat: Beat) -> None:
        from manim import DOWN, Text, VGroup, Write

        self._transition_to({})

        summary = Text("Bias = wrong assumptions. Variance = sensitivity to data.", font_size=26)
        note = Text("Find the sweet spot.", font_size=22, color="#FFD700")
        note.next_to(summary, DOWN)
        others = VGroup(summary, note)
        self.play(Write(others))
        self._state["recap"] = others


ConceptRegistry.register(BiasVarianceExtension())
