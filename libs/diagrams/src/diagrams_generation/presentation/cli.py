import argparse
import sys
from pathlib import Path

from diagrams_generation.adapters.logging import setup_structured_logging
from diagrams_generation.adapters.mingrammer_renderer import (
    MingrammerDiagramRenderer,
)
from diagrams_generation.core.loader import load_from_file


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Declarative diagram generator"
    )
    parser.add_argument(
        "diagram_id", help="The name of the diagram definition file"
    )
    parser.add_argument(
        "--definitions-dir",
        default="diagrams/definition",
        help="Directory containing diagram yaml definitions",
    )
    parser.add_argument(
        "--output-dir",
        default="diagrams/output",
        help="Directory where rendered diagrams will be saved",
    )
    return parser.parse_args()


def main() -> None:
    setup_structured_logging()
    arguments = _parse_arguments()
    definitions_directory = Path(arguments.definitions_dir)
    yaml_path = definitions_directory / f"{arguments.diagram_id}.yaml"

    try:
        if not yaml_path.exists():
            yaml_path = definitions_directory / f"{arguments.diagram_id}.yml"
        if not yaml_path.exists():
            raise FileNotFoundError(
                f"Missing diagram definition: {arguments.diagram_id} "
                f"(expected file at {yaml_path})"
            )
        definition = load_from_file(yaml_path)
        renderer = MingrammerDiagramRenderer()
        renderer.render(definition, arguments.output_dir)
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
