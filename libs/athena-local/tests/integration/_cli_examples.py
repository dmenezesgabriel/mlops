"""CS-3 input: the AWS CLI athena example commands from the installed awscli.

The CLI ships its own examples as package data (``recursive-include
awscli/examples *.rst`` in the awscli MANIFEST.in); reading them from the
installed distribution keeps the consumer under test and the commands it
runs from the same artifact, mirroring how the parity loop reads the
installed botocore model. The frozen checkout at
``research_repos/aws-cli/awscli/examples/athena/`` is the byte-identical
reference anchor.

Each literal block after ``::`` that starts with an indented ``aws athena``
line becomes one argv token list: backslash continuations are joined, written
quotes are stripped (escaping inside the value is preserved verbatim, which
is exactly what a shell would pass to the CLI's argument parser).
"""

from __future__ import annotations

import re
from importlib.resources import files

_COMMAND_START = re.compile(r"^\s{2,}aws athena ")
_INDENTED_LINE = re.compile(r"^\s{4,}\S")


def example_stems() -> list[str]:
    """The ``.rst`` stems of every athena example the CLI ships."""
    directory = files("awscli") / "examples" / "athena"
    stems = sorted(
        path.name[: -len(".rst")]
        for path in directory.iterdir()
        if path.name.endswith(".rst")
    )
    return stems


def load_example(stem: str) -> list[list[str]]:
    """The argv token lists for one example file (``get-work-group`` etc.)."""
    path = files("awscli") / "examples" / "athena" / f"{stem}.rst"
    return extract_command_tokens(path.read_text())


def extract_command_tokens(rst_text: str) -> list[list[str]]:
    """Every ``aws athena …`` block in a doc excerpt, as argv token lists."""
    commands: list[list[str]] = []
    lines = rst_text.splitlines()
    index = 0
    while index < len(lines):
        if _COMMAND_START.match(lines[index]):
            block = [lines[index].strip()]
            index += 1
            while index < len(lines) and _INDENTED_LINE.match(lines[index]):
                block.append(lines[index].strip())
                index += 1
            commands.append(_tokenize(block))
        else:
            index += 1
    return commands


def _tokenize(block: list[str]) -> list[str]:
    """Join continuations, then split with shell double-quote semantics.

    A double-quoted segment groups spaces and is stripped, mid-token quotes
    continue the same token (``Key=Team,Value="Big Data"`` → one argv
    element), and ``\\"``/``\\\\`` inside quotes unescape — matching what a
    shell passes to the CLI's argument parser.
    """
    text = " ".join(
        line[:-1] if line.endswith("\\") else line for line in block
    )
    tokens: list[str] = []
    current: list[str] = []
    in_quotes = False
    index = 0
    while index < len(text):
        char = text[index]
        if char == '"':
            in_quotes = not in_quotes
        elif char.isspace() and not in_quotes:
            if current:
                tokens.append("".join(current))
                current = []
        elif char == "\\" and in_quotes and index + 1 < len(text):
            current.append(text[index + 1])
            index += 1
        else:
            current.append(char)
        index += 1
    if current:
        tokens.append("".join(current))
    return tokens
