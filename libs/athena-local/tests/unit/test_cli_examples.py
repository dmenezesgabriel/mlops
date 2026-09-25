"""Unit tests for the CS-3 example-command extractor (``_cli_examples``).

The extractor turns the ``aws athena …`` literal blocks awscli ships in
``examples/athena/*.rst`` into argv token lists. It is pure (text in, tokens
out) so these tests need no installed package — the fixture text mirrors the
real block shapes: prose first, a ``::``-fenced block, backslash
continuations, quoted values with embedded spaces, and multiple examples per
file (the CLI ships multi-example files such as ``start-query-execution``).
"""

from __future__ import annotations

from tests.integration._cli_examples import extract_command_tokens

SINGLE_COMMAND_RST = """
**To return information about a workgroup**

The following ``get-work-group`` example returns information about the
``AthenaAdmin`` workgroup. ::

    aws athena get-work-group \\
        --work-group AthenaAdmin

Output::

    {
        "WorkGroup": {
            "Name": "AthenaAdmin"
        }
    }
"""

MULTI_COMMAND_RST = """
**Example 1: to run a query**

::

    aws athena start-query-execution \\
        --query-string "select date from cloudfront_logs limit 10" \\
        --work-group "AthenaAdmin" \\
        --query-execution-context Database=cflogsdatabase,Catalog=AwsDataCatalog

**Example 2: to create a database**

::

    aws athena start-query-execution \\
        --query-string "create database if not exists newdb"
"""

QUOTED_ESCAPE_RST = """
The following ``create-named-query`` example saves a query. ::

    aws athena create-named-query \\
        --name "SEA to JFK delayed flights Jan 2016" \\
        --database sampledb \\
        --query-string "SELECT origin = '\\"SEA\\"' AND status = 200"
"""


def test_single_command_is_one_token_list() -> None:
    tokens = extract_command_tokens(SINGLE_COMMAND_RST)

    assert tokens == [
        ["aws", "athena", "get-work-group", "--work-group", "AthenaAdmin"]
    ]


def test_multiple_examples_in_one_file_each_become_a_command() -> None:
    tokens = extract_command_tokens(MULTI_COMMAND_RST)

    assert tokens[0] == [
        "aws",
        "athena",
        "start-query-execution",
        "--query-string",
        "select date from cloudfront_logs limit 10",
        "--work-group",
        "AthenaAdmin",
        "--query-execution-context",
        "Database=cflogsdatabase,Catalog=AwsDataCatalog",
    ]
    assert tokens[1] == [
        "aws",
        "athena",
        "start-query-execution",
        "--query-string",
        "create database if not exists newdb",
    ]


def test_quoted_values_keep_embedded_spaces_and_escape_sequences() -> None:
    tokens = extract_command_tokens(QUOTED_ESCAPE_RST)[0]

    assert tokens[4] == "SEA to JFK delayed flights Jan 2016"
    # \” unescapes inside the quoted value, exactly as a shell passes it.
    assert tokens[8] == "SELECT origin = '\"SEA\"' AND status = 200"


def test_mid_token_quote_groups_without_splitting_the_token() -> None:
    tokens = extract_command_tokens(
        "    aws athena create-work-group --tags "
        'Key=Division,Value=West Key=Team,Value="Big Data"\n'
    )[0]

    assert tokens[4:] == [
        "Key=Division,Value=West",
        "Key=Team,Value=Big Data",
    ]


def test_unindented_text_is_never_treated_as_a_command() -> None:
    tokens = extract_command_tokens(
        "aws athena list-work-groups\n\n    aws athena get-work-group\n"
    )

    assert tokens == [["aws", "athena", "get-work-group"]]
