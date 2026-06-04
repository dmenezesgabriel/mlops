from manim import Scene, Text


class BiasVarianceTradeoff(Scene):
    def construct(self) -> None:
        title = Text("Bias-Variance Tradeoff")
        self.play(title.animate.scale(1.1))
        self.wait(1)
