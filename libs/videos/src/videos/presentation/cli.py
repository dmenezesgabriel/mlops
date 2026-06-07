from __future__ import annotations

import argparse
import sys
from pathlib import Path

from videos.application.components import ComponentRegistry
from videos.application.director import Director
from videos.application.ports.telemetry import Telemetry
from videos.infrastructure.declarative import register_all
from videos.infrastructure.filesystem.artifact_store import (
    FileSystemArtifactStore,
)
from videos.infrastructure.logging.structured_logger import (
    setup_structured_logging,
)
from videos.infrastructure.manim.components import register_default_components
from videos.infrastructure.manim.layout_engine import ManimLayoutEngine
from videos.infrastructure.manim.renderer import ManimRenderer
from videos.infrastructure.manim.scene_builder import ManimSceneBuilder
from videos.infrastructure.validation.linter_service import LinterService


class ConsoleTelemetry(Telemetry):
    def record_event(
        self, event_name: str, attributes: dict[str, object]
    ) -> None:
        print(f"[EVENT] {event_name}: {attributes}")

    def record_error(
        self, error: Exception, attributes: dict[str, object]
    ) -> None:
        print(f"[ERROR] {error}: {attributes}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render Manim concept videos using the Director pipeline."
    )
    parser.add_argument("concept_id", help="The ID of the concept to render.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Root directory for artifacts.",
    )
    parser.add_argument(
        "--definitions-dir",
        type=Path,
        default=Path("videos/definition"),
        help="Directory containing concept YAML definitions.",
    )
    parser.add_argument(
        "--quality",
        choices=["preview", "final"],
        default="preview",
        help="The quality of the video production.",
    )

    args = parser.parse_args()

    setup_structured_logging()
    register_all(definitions_dir=args.definitions_dir)

    registry = ComponentRegistry()
    register_default_components(registry)

    renderer = ManimRenderer()
    scene_builder = ManimSceneBuilder(registry=registry)
    layout_engine = ManimLayoutEngine()
    artifact_store = FileSystemArtifactStore(output_root=args.output_dir)
    telemetry = ConsoleTelemetry()
    linter_service = LinterService()

    director = Director(
        concept_id=args.concept_id,
        renderer=renderer,
        scene_builder=scene_builder,
        layout_engine=layout_engine,
        artifact_store=artifact_store,
        telemetry=telemetry,
        linter_service=linter_service,
    )

    try:
        director.produce(quality=args.quality)
        print(
            f"Successfully produced video for concept: {args.concept_id} (quality={args.quality})"
        )
    except Exception as e:
        print(f"Failed to produce video: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
