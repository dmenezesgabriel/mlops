"""Bridge moto Glue operations that the Trino hive connector requires.

moto 5.1.16 (and upstream master) implements no column-statistics or
user-defined-function operations in its Glue backend. Trino's hive connector,
driven against moto Glue per ADR-0005, depends on four of them:
``UpdateColumnStatisticsForTable`` and ``DeleteColumnStatisticsForTable`` are
called after every create-table commit (SemiTransactionalHiveMetastore
CreateTableOperation; ``hive.collect-column-statistics-on-write`` does not
gate that path), and ``GetUserDefinedFunctions`` backs ``SHOW FUNCTIONS``.
Without them every CREATE TABLE / CTAS against the hive catalog fails with
moto's HTTP 500.

This module attaches exactly those operations to the running moto server
classes: thin handlers on ``GlueResponse`` plus storage on a per-backend
weak map. Wire shapes follow the Glue service model vendored by botocore at
``research_repos/aws-cli/awscli/botocore/data/glue/2017-03-31/service-2.json``.
Only the moto service container runs this module (docker/trino entrypoint);
the athena-local library never imports it (ADR-0008).
"""

from __future__ import annotations

import fnmatch
from typing import TypeAlias
from weakref import WeakKeyDictionary

from moto.core.responses import ActionResult, EmptyResult
from moto.glue.exceptions import InvalidInputException
from moto.glue.models import GlueBackend
from moto.glue.responses import GlueResponse

ColumnStatistics: TypeAlias = dict[str, object]
UserDefinedFunction: TypeAlias = dict[str, object]

# Both stores are keyed by the Glue backend instance so moto's
# per-(account, region) reset across mock_glue() boundaries yields fresh
# empty state without touching moto's own constructors.
_column_statistics: WeakKeyDictionary[
    GlueBackend, dict[tuple[str, str], dict[str, ColumnStatistics]]
] = WeakKeyDictionary()
_user_defined_functions: WeakKeyDictionary[
    GlueBackend, dict[str, dict[str, UserDefinedFunction]]
] = WeakKeyDictionary()


def as_string(value: object, operation: str) -> str:
    if not isinstance(value, str):
        raise InvalidInputException(
            operation,
            f"expected string, got {type(value).__name__}: {value!r}",
        )
    return value


def _column_name(entry: ColumnStatistics) -> str:
    value = entry.get("ColumnName")
    if not isinstance(value, str):
        raise InvalidInputException(
            "updateColumnStatisticsForTable",
            f"expected string ColumnName, got {type(value).__name__}: {value!r}",
        )
    return value


def update_column_statistics(
    this: GlueBackend,
    database_name: str,
    table_name: str,
    statistics: list[ColumnStatistics],
) -> None:
    this.get_table(database_name, table_name)
    store = _column_statistics.setdefault(this, {}).setdefault(
        (database_name, table_name), {}
    )
    store.update((_column_name(entry), entry) for entry in statistics)


def delete_column_statistics(
    this: GlueBackend, database_name: str, table_name: str, column_name: str
) -> None:
    # Deleting statistics for an unknown column is a no-op: AWS returns
    # success, and Trino drops every column without collected statistics on
    # OVERWRITE_ALL commits.
    this.get_table(database_name, table_name)
    stores = _column_statistics.get(this)
    if stores is None:
        return
    stores.get((database_name, table_name), {}).pop(column_name, None)


def get_column_statistics(
    this: GlueBackend, database_name: str, table_name: str
) -> list[ColumnStatistics]:
    this.get_table(database_name, table_name)
    stores = _column_statistics.get(this)
    if stores is None:
        return []
    return list(stores.get((database_name, table_name), {}).values())


def resolve_user_defined_functions(
    this: GlueBackend, database_name: str | None, pattern: str
) -> list[UserDefinedFunction]:
    stores = _matching_stores(this, database_name)
    return _matching_functions(stores, pattern)


def _matching_stores(
    this: GlueBackend, database_name: str | None
) -> list[dict[str, UserDefinedFunction]]:
    all_stores = _user_defined_functions.get(this)
    if database_name is not None:
        # A call scoped to a missing database is an error, matching AWS Glue.
        this.get_database(database_name)
    if all_stores is None:
        return []
    if database_name is None:
        return list(all_stores.values())
    return [all_stores.get(database_name, {})]


def _matching_functions(
    stores: list[dict[str, UserDefinedFunction]], pattern: str
) -> list[UserDefinedFunction]:
    return [
        function
        for store in stores
        for name, function in store.items()
        if fnmatch.fnmatchcase(name, pattern)
    ]


def update_column_statistics_for_table(self: GlueResponse) -> EmptyResult:
    parameters = self.parameters
    statistics = parameters.get("ColumnStatisticsList")
    if not isinstance(statistics, list):
        raise InvalidInputException(
            "updateColumnStatisticsForTable",
            f"expected list, got {type(statistics).__name__}: {statistics!r}",
        )
    update_column_statistics(
        self.glue_backend,
        as_string(
            parameters.get("DatabaseName"), "updateColumnStatisticsForTable"
        ),
        as_string(
            parameters.get("TableName"), "updateColumnStatisticsForTable"
        ),
        statistics,
    )
    return EmptyResult()


def delete_column_statistics_for_table(self: GlueResponse) -> EmptyResult:
    parameters = self.parameters
    delete_column_statistics(
        self.glue_backend,
        as_string(
            parameters.get("DatabaseName"), "deleteColumnStatisticsForTable"
        ),
        as_string(
            parameters.get("TableName"), "deleteColumnStatisticsForTable"
        ),
        as_string(
            parameters.get("ColumnName"), "deleteColumnStatisticsForTable"
        ),
    )
    return EmptyResult()


def get_column_statistics_for_table(self: GlueResponse) -> ActionResult:
    parameters = self.parameters
    statistics = get_column_statistics(
        self.glue_backend,
        as_string(
            parameters.get("DatabaseName"), "getColumnStatisticsForTable"
        ),
        as_string(parameters.get("TableName"), "getColumnStatisticsForTable"),
    )
    return ActionResult({"ColumnStatisticsList": statistics})


def get_user_defined_functions(self: GlueResponse) -> ActionResult:
    parameters = self.parameters
    functions = resolve_user_defined_functions(
        self.glue_backend,
        _optional_string(
            parameters.get("DatabaseName"), "getUserDefinedFunctions"
        ),
        _pattern(parameters.get("Pattern")),
    )
    return ActionResult({"UserDefinedFunctions": functions})


def _optional_string(value: object, operation: str) -> str | None:
    if value is None:
        return None
    return as_string(value, operation)


def _pattern(value: object) -> str:
    if value is None:
        return "*"
    return as_string(value, "getUserDefinedFunctions")


_RESPONSE_OPERATIONS: dict[str, object] = {
    "update_column_statistics_for_table": update_column_statistics_for_table,
    "delete_column_statistics_for_table": delete_column_statistics_for_table,
    "get_column_statistics_for_table": get_column_statistics_for_table,
    "get_user_defined_functions": get_user_defined_functions,
}


def apply_overlay() -> None:
    """Attach the four Glue operations to the running moto server classes."""
    if getattr(GlueResponse, "get_user_defined_functions", None) is not None:
        return
    for operation, handler in _RESPONSE_OPERATIONS.items():
        setattr(GlueResponse, operation, handler)
