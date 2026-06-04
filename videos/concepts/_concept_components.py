from dataclasses import dataclass

from manim import DOWN, RIGHT, UP, Arrow, Circle, FadeIn, FadeOut, Scene, Text, VGroup, Write


@dataclass(frozen=True)
class ConceptStep:
    title: str
    note: str


class FlowDiagramScene(Scene):
    title: str
    subtitle: str
    steps: tuple[ConceptStep, ...]

    def construct(self) -> None:
        title_group = self._title_group()
        flow_group = self._flow_group()
        self.play(Write(title_group))
        self.play(FadeIn(flow_group, shift=UP))
        self.wait(2)
        self.play(FadeOut(flow_group), FadeOut(title_group))

    def _title_group(self) -> VGroup:
        title = Text(self.title, font_size=40)
        subtitle = Text(self.subtitle, font_size=22).next_to(title, DOWN, buff=0.25)
        return VGroup(title, subtitle).to_edge(UP)

    def _flow_group(self) -> VGroup:
        nodes = VGroup(*(self._node(step) for step in self.steps)).arrange(RIGHT, buff=0.8)
        arrows = VGroup(
            *(
                Arrow(nodes[index].get_right(), nodes[index + 1].get_left())
                for index in range(len(nodes) - 1)
            ),
        )
        return VGroup(nodes, arrows).move_to(DOWN * 0.35)

    def _node(self, step: ConceptStep) -> VGroup:
        circle = Circle(radius=0.75)
        title = Text(step.title, font_size=20).move_to(circle.get_center() + UP * 0.12)
        note = Text(step.note, font_size=14).next_to(circle, DOWN, buff=0.2)
        return VGroup(circle, title, note)
