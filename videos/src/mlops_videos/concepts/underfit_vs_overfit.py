from __future__ import annotations

import math

from mlops_videos.adapters._manim._scene import ConceptScene
from mlops_videos.concepts._base import ConceptExtension
from mlops_videos.concepts._registry import ConceptRegistry
from mlops_videos.core._domain._concept import Concept, ConceptId, ConceptMetadata, ConceptTitle
from mlops_videos.core._domain._narrative import Beat, BeatKind, NarrationLine, Narrative


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
                        "Underfitting vs Overfitting. \
Too simple or too complex.",
                        5.0,
                    ),
                    "title",
                    {},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Here is our training data. \
Points that follow a clear pattern with some noise mixed in. \
A good model captures the pattern, not the noise.",
                        7.0,
                    ),
                    "data_points",
                    {},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Underfitting. The model is too simple. \
A straight line through curved data. \
It misses the pattern entirely. \
High training error and high validation error.",
                        9.0,
                    ),
                    "underfit",
                    {},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Overfitting. The model is too complex. \
It memorizes every single data point, including the noise. \
Zero training error but terrible validation error.",
                        9.0,
                    ),
                    "overfit",
                    {},
                ),
                Beat(
                    BeatKind.EMPHASIS,
                    NarrationLine(
                        "Just right. Captures the underlying pattern without the noise. \
Good training error AND good validation error. \
This is what we want.",
                        7.0,
                    ),
                    "just_right",
                    {},
                ),
                Beat(
                    BeatKind.TRANSITION,
                    NarrationLine(
                        "How to tell which problem you have? \
Look at your validation error. Both high = underfit. \
Low training + high validation = overfit.",
                        7.0,
                    ),
                    "diagnosis",
                    {},
                ),
                Beat(
                    BeatKind.TRANSITION,
                    NarrationLine(
                        "Fix overfitting with regularization. \
It adds a penalty for complexity. \
Fix underfitting with more features or a bigger model.",
                        7.0,
                    ),
                    "regularization",
                    {},
                ),
                Beat(
                    BeatKind.TRANSITION,
                    NarrationLine(
                        "The training error always goes down. \
But the validation error tells the real story. \
It drops, then rises again. That rise is overfitting.",
                        8.0,
                    ),
                    "learning_curves",
                    {},
                ),
                Beat(
                    BeatKind.RECAP,
                    NarrationLine(
                        "Underfit needs more model: more features, more complexity. \
Overfit needs more data or regularization. \
Your validation set tells you which one you've got.",
                        8.0,
                    ),
                    "recap",
                    {},
                ),
            ),
        )


class UnderfitVsOverfitScene(ConceptScene):
    concept_id = "underfit_vs_overfit"

    def _on_opening_title(self, _beat: Beat) -> None:
        from manim import DOWN, UP, Text, VGroup, Write

        title = Text("Underfitting vs Overfitting", font_size=40)
        subtitle = Text("Too simple or too complex", font_size=22)
        subtitle.next_to(title, DOWN)
        group = VGroup(title, subtitle).to_edge(UP)
        self.play(Write(group))
        self._state["title_group"] = group

    def _on_reveal_data_points(self, beat: Beat) -> None:
        from manim import Create

        from mlops_videos.adapters._manim._graph_builder import GraphBuilder

        axes = GraphBuilder.create_axes(
            self,
            x_range=(0, 6, 1),
            y_range=(0, 6, 1),
        )
        axes.scale(0.8).shift([0, 0.2, 0])
        self.play(Create(axes))
        self._state["axes"] = axes

        points: list[tuple[float, float]] = []
        for x in range(0, 60):
            xf = x / 10.0
            yf = math.sin(xf) + 3.0 + (x % 7 - 3) * 0.15
            if 0 <= xf <= 6 and 0 <= yf <= 6:
                points.append((xf, yf))

        data = GraphBuilder.plot_data(self, axes, points, color="#AAAAAA", radius=0.05)
        self.play(Create(data))
        self._state["data_points"] = data
        self._raw_points = points
        self.wait(beat.narration.duration_seconds * 0.25)

    def _on_reveal_underfit(self, beat: Beat) -> None:
        from manim import DOWN, Create, Text

        axes = self._state.get("axes")
        if axes is None:
            return

        line = axes.plot(lambda x: x * 0.3 + 1.5, x_range=(0, 6), color="#E74C3C")
        self.play(Create(line))
        self._state["underfit_line"] = line

        label = Text("Underfit: too simple", font_size=18, color="#E74C3C")
        label.next_to(self._state.get("data_points", axes), DOWN, buff=0.5)
        self.play(Create(label))
        self._state["underfit_label"] = label
        self.wait(beat.narration.duration_seconds * 0.25)

    def _on_reveal_overfit(self, beat: Beat) -> None:
        from manim import DOWN, Create, Text

        self._clear_state("underfit_line", "underfit_label")

        axes = self._state.get("axes")
        if axes is None:
            return

        points = getattr(self, "_raw_points", [])
        if not points:
            return

        def overfit_func(x: float) -> float:
            total = 0.0
            for px, py in points[::3]:
                dx = x - px
                total += py * math.exp(-dx * dx * 5.0)
            return total / max(
                sum(math.exp(-((x - px) ** 2) * 5.0) for px, _ in points[::3]), 0.001
            )

        wiggly = axes.plot(overfit_func, x_range=(0, 6), color="#FF8C42")
        self.play(Create(wiggly))
        self._state["overfit_line"] = wiggly

        label = Text("Overfit: memorizes noise", font_size=18, color="#FF8C42")
        label.next_to(self._state.get("data_points", axes), DOWN, buff=0.5)
        self.play(Create(label))
        self._state["overfit_label"] = label
        self.wait(beat.narration.duration_seconds * 0.25)

    def _on_emphasis_just_right(self, beat: Beat) -> None:
        from manim import DOWN, Create, Text

        self._clear_state("overfit_line", "overfit_label")

        axes = self._state.get("axes")
        if axes is None:
            return

        def good_fit(x: float) -> float:
            return math.sin(x) + 3.0

        good = axes.plot(good_fit, x_range=(0, 6), color="#00FF00")
        self.play(Create(good))
        self._state["good_line"] = good

        label = Text("Just right: captures the pattern", font_size=18, color="#00FF00")
        label.next_to(self._state.get("data_points", axes), DOWN, buff=0.5)
        self.play(Create(label))
        self._state["just_right_label"] = label
        self.wait(beat.narration.duration_seconds * 0.25)

    def _on_transition_diagnosis(self, beat: Beat) -> None:
        from manim import DOWN, Text, VGroup, Write

        self._transition_to({})

        tips = VGroup(
            Text("High train + High val  =  Underfit", font_size=22, color="#E74C3C"),
            Text("Low train  + High val  =  Overfit", font_size=22, color="#FF8C42"),
        ).arrange(DOWN, buff=0.4)
        self.play(Write(tips))
        self._state["diagnosis_tips"] = tips
        self.wait(beat.narration.duration_seconds * 0.25)

    def _on_transition_regularization(self, beat: Beat) -> None:
        from manim import Text, Write

        self._transition_to({})

        note = Text(
            "Fix overfit: Regularization (penalty for complexity). \
Fix underfit: More features or bigger model.",
            font_size=22,
            color="#00FF00",
        )
        self.play(Write(note))
        self._state["regularization_note"] = note
        self.wait(beat.narration.duration_seconds * 0.25)

    def _on_transition_learning_curves(self, beat: Beat) -> None:
        from manim import RIGHT, Create, Text, VGroup

        from mlops_videos.adapters._manim._graph_builder import GraphBuilder

        self._transition_to({})

        axes = GraphBuilder.create_axes(
            self,
            x_range=(0, 10, 1),
            y_range=(0, 5, 1),
        )
        axes.scale(0.7).shift([0.5, 0, 0])
        self.play(Create(axes))
        self._state["learning_axes"] = axes

        def train_err(x: float) -> float:
            return 4.0 * math.exp(-0.4 * x) + 0.2

        def val_err(x: float) -> float:
            return 0.08 * (x - 6) ** 2 + 0.5

        train_plot = axes.plot(train_err, x_range=(0, 10), color="#50C878")
        val_plot = axes.plot(val_err, x_range=(0, 10), color="#E74C3C")
        self.play(Create(train_plot), Create(val_plot))
        self._state["train_curve"] = train_plot
        self._state["val_curve"] = val_plot

        train_label = Text("Training error", font_size=14, color="#50C878")
        train_label.next_to(axes.c2p(9, 0.3), RIGHT, buff=0.2)
        val_label = Text("Validation error", font_size=14, color="#E74C3C")
        val_label.next_to(axes.c2p(9, 2.0), RIGHT, buff=0.2)
        labels = VGroup(train_label, val_label)
        self.play(Create(labels))
        self._state["curve_labels"] = labels

    def _on_recap_recap(self, beat: Beat) -> None:
        from manim import DOWN, Text, VGroup, Write

        self._transition_to({})

        summary = VGroup(
            Text("Underfit: not enough model capacity", font_size=22, color="#E74C3C"),
            Text("Overfit: too much model capacity", font_size=22, color="#FF8C42"),
            Text("Validation error tells you which", font_size=22, color="#00FF00"),
        ).arrange(DOWN, buff=0.3)
        for item in summary:
            self.play(Write(item))
            self.wait(0.2)

        self._state["recap"] = summary
        self.wait(beat.narration.duration_seconds * 0.15)


ConceptRegistry.register(UnderfitOverfitExtension())
