from typing import Protocol

from diagrams_generation.domain.diagram import DiagramDefinition


class DiagramRendererPort(Protocol):
    def render(
        self, definition: DiagramDefinition, output_directory: str
    ) -> str:
        """Render a diagram definition into the output directory.

        Returns the absolute or relative path to the generated image file.
        """
        ...
