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

It also bridges two GetPartitions expression gaps that block every Trino
partitioned read: moto 5.1.16 raises ``Unsupported expression ''``
for the blank ``Expression`` the Hive metastore client sends when listing all
partitions (upstream fix ``4db88f3a4`` / ``#10122``), and its ``_cast`` only
knows bare type names while Trino registers keys as ``varchar(2)``,
``decimal(10,2)``, ``timestamp(3)`` and ``char(N)``.

Finally it injects AWS Glue's Iceberg column markers at table-registration
time: real Athena writes ``iceberg.field.*`` parameters onto every column of
an Iceberg table's Glue record (its Iceberg engine owns them), Trino's Glue
catalog does not, and awswrangler's ``get_table_types(
filter_iceberg_current=True)`` filters on ``iceberg.field.current`` — without
the marker a second ``to_iceberg`` call reads an empty schema and rejects its
own frame as a schema change.

Only the moto service container runs this module (docker/trino entrypoint);
the athena-local library never imports it (ADR-0008).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, TypeAlias, cast
from weakref import WeakKeyDictionary

from moto.core.responses import ActionResult, EmptyResult
from moto.glue import utils as glue_utils
from moto.glue.exceptions import InvalidInputException
from moto.glue.models import FakeTable, GlueBackend
from moto.glue.responses import GlueResponse

# pyright: reportPrivateUsage=false
# This module is a moto overlay: it monkey-patches moto.glue internals
# (_PartitionFilterExpressionCache, glue_utils._cast, _Expr) on purpose.
from moto.glue.utils import _PartitionFilterExpressionCache

ColumnStatistics: TypeAlias = dict[str, object]

# The store is keyed by the Glue backend instance so moto's
# per-(account, region) reset across mock_glue() boundaries yields fresh
# empty state without touching moto's own constructors.
_column_statistics: WeakKeyDictionary[
    GlueBackend, dict[tuple[str, str], dict[str, ColumnStatistics]]
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
    this: GlueBackend,
    database_name: str,
    table_name: str,
    column_names: list[str],
) -> list[ColumnStatistics]:
    this.get_table(database_name, table_name)
    stores = _column_statistics.get(this)
    if stores is None:
        return []
    table_store = stores.get((database_name, table_name), {})
    return [table_store[name] for name in column_names if name in table_store]


def update_column_statistics_for_table(self: GlueResponse) -> EmptyResult:
    parameters = self.parameters
    statistics = parameters.get("ColumnStatisticsList")
    if not isinstance(statistics, list):
        raise InvalidInputException(
            "updateColumnStatisticsForTable",
            f"expected list, got {type(statistics).__name__}: {statistics!r}",
        )
    entries: list[object] = statistics
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise InvalidInputException(
                "updateColumnStatisticsForTable",
                f"expected dict at ColumnStatisticsList[{index}], "
                f"got {type(entry).__name__}: {entry!r}",
            )
    statistics_list = cast(list[ColumnStatistics], entries)
    update_column_statistics(
        self.glue_backend,
        as_string(
            parameters.get("DatabaseName"), "updateColumnStatisticsForTable"
        ),
        as_string(
            parameters.get("TableName"), "updateColumnStatisticsForTable"
        ),
        statistics_list,
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
    column_names = parameters.get("ColumnNames")
    if not isinstance(column_names, list):
        raise InvalidInputException(
            "getColumnStatisticsForTable",
            f"expected list, got {type(column_names).__name__}: "
            f"{column_names!r}",
        )
    statistics = get_column_statistics(
        self.glue_backend,
        as_string(
            parameters.get("DatabaseName"), "getColumnStatisticsForTable"
        ),
        as_string(parameters.get("TableName"), "getColumnStatisticsForTable"),
        [
            as_string(name, "getColumnStatisticsForTable")
            for name in cast(list[object], column_names)
        ],
    )
    return ActionResult({"ColumnStatisticsList": statistics})


def get_user_defined_functions(self: GlueResponse) -> ActionResult:
    # moto ships no UDF write op, so the list is always empty; scoping the
    # call to a missing database is still an error, matching AWS Glue.
    database_name = self.parameters.get("DatabaseName")
    if database_name is not None:
        self.glue_backend.get_database(
            as_string(database_name, "getUserDefinedFunctions")
        )
    return ActionResult({"UserDefinedFunctions": []})


_RESPONSE_OPERATIONS: dict[str, object] = {
    "update_column_statistics_for_table": update_column_statistics_for_table,
    "delete_column_statistics_for_table": delete_column_statistics_for_table,
    "get_column_statistics_for_table": get_column_statistics_for_table,
    "get_user_defined_functions": get_user_defined_functions,
}

# Trino registers partition keys with their full Hive spelling; these scalars
# fold onto branches moto's _cast already implements (float data, string
# data, integral data).
_SCALAR_TYPE_FOLDS: dict[str, str] = {
    "boolean": "string",
    "double": "decimal",
    "float": "decimal",
    "integer": "bigint",
    "real": "decimal",
}

_ORIGINAL_PARTITION_CAST = glue_utils._cast
_ORIGINAL_FILTER_EXPRESSION_GET = _PartitionFilterExpressionCache.get


def _normalize_partition_type(type_: str) -> str:
    """Reduce a Hive/Trino partition key type to a bare moto _cast type.

    Stops ``varchar(2)``/``decimal(10,2)``/``timestamp(3)``/``char(N)`` at the
    first ``(`` and folds the remaining real-AWS scalars (double, float, real,
    boolean, integer) onto the branch moto implements. Registered spellings
    arrive verbatim while moto only knows bare lowercase names, so
    ``VARCHAR(2)`` and ``decimal (10,2)`` must normalize case and
    whitespace as well.
    """
    base = type_.split("(", 1)[0].strip().lower()
    return _SCALAR_TYPE_FOLDS.get(base, base)


def _cast_partition_value(
    type_: str, value: object
) -> date | datetime | float | int | str:
    """Cast a partition value after normalizing its key's Hive type spelling."""
    return _ORIGINAL_PARTITION_CAST(_normalize_partition_type(type_), value)


def _get_filter_expression(
    self: _PartitionFilterExpressionCache, expression: str | None
) -> glue_utils._Expr | None:
    # Real AWS Glue treats a blank Expression as "no filter", and the Hive
    # metastore Glue client sends Expression='' when listing all partitions.
    # Upstream moto #10122 (4db88f3a4) mirrors that; 5.1.16 only special-cases
    # None, so the empty string fails the grammar parse.
    if expression is None or not expression.strip():
        return None
    return _ORIGINAL_FILTER_EXPRESSION_GET(self, expression)


_ORIGINAL_CREATE_TABLE = GlueBackend.create_table
_ORIGINAL_UPDATE_TABLE = GlueBackend.update_table
_ORIGINAL_DELETE_TABLE = GlueBackend.delete_table
_ORIGINAL_DELETE_DATABASE = GlueBackend.delete_database


def _mark_iceberg_columns(table_input: dict[str, Any]) -> None:
    """Inject AWS Glue's Iceberg column markers into a table registration.

    Real Athena writes ``iceberg.field.*`` parameters onto every column of
    an Iceberg table's Glue record; Trino's Glue catalog does not, and
    awswrangler's ``get_table_types(filter_iceberg_current=True)`` filters
    on ``iceberg.field.current`` — the marker is what keeps a second
    ``to_iceberg`` call from reading an empty schema.
    """
    parameters = table_input.get("Parameters")
    if not isinstance(parameters, dict):
        return
    parameter_map = cast(dict[str, Any], parameters)
    if str(parameter_map.get("table_type", "")).upper() != "ICEBERG":
        return
    storage = table_input.get("StorageDescriptor")
    if not isinstance(storage, dict):
        return
    storage_map = cast(dict[str, Any], storage)
    columns = storage_map.get("Columns")
    if not isinstance(columns, list):
        return
    for column in cast(list[Any], columns):
        if not isinstance(column, dict):
            continue
        column_map = cast(dict[str, Any], column)
        column_parameters = column_map.setdefault("Parameters", {})
        if not isinstance(column_parameters, dict):
            continue
        cast(dict[str, Any], column_parameters)["iceberg.field.current"] = (
            "true"
        )


# Wrappers keep moto's exact (self, Any) signatures — pyright checks the
# assignment against the real attributes.
def create_table_with_iceberg_markers(
    self: GlueBackend,
    database_name: str,
    table_name: str,
    table_input: dict[str, Any],
) -> FakeTable:
    _mark_iceberg_columns(table_input)
    return _ORIGINAL_CREATE_TABLE(self, database_name, table_name, table_input)


def update_table_with_iceberg_markers(
    self: GlueBackend,
    database_name: str,
    table_name: str,
    table_input: dict[str, Any],
) -> None:
    _mark_iceberg_columns(table_input)
    _ORIGINAL_UPDATE_TABLE(self, database_name, table_name, table_input)


# Column statistics live on (database, table) name keys in the side store,
# not on the FakeTable, so moto's deletes strand them: a recreated table
# would read its previous incarnation's numbers, and the store grows one
# key per drop cycle. Purge only after the real delete succeeds — a
# raising delete changes nothing.
def delete_table_with_statistics_purge(
    self: GlueBackend,
    database_name: str,
    table_name: str,
) -> None:
    _ORIGINAL_DELETE_TABLE(self, database_name, table_name)
    stores = _column_statistics.get(self)
    if stores is None:
        return
    stores.pop((database_name, table_name), None)


def delete_database_with_statistics_purge(
    self: GlueBackend,
    database_name: str,
) -> None:
    _ORIGINAL_DELETE_DATABASE(self, database_name)
    stores = _column_statistics.get(self)
    if stores is None:
        return
    for key in [key for key in stores if key[0] == database_name]:
        del stores[key]


# Patches must stay module-global lookups to work: PartitionFilter resolves
# _PARTITION_FILTER_EXPRESSION_CACHE.get on the class, _Ident/_Like call
# _cast by name inside moto.glue.utils, and the Iceberg column markers
# belong on the stored table — not a response shim — so update_table is
# wrapped too, keeping them flowing through ALTER ADD COLUMN writes.
_PATCHES: tuple[tuple[object, str, object], ...] = (
    (_PartitionFilterExpressionCache, "get", _get_filter_expression),
    (glue_utils, "_cast", _cast_partition_value),
    (GlueBackend, "create_table", create_table_with_iceberg_markers),
    (GlueBackend, "update_table", update_table_with_iceberg_markers),
    (GlueBackend, "delete_table", delete_table_with_statistics_purge),
    (GlueBackend, "delete_database", delete_database_with_statistics_purge),
)


def apply_overlay() -> None:
    """Attach the Glue bridges to the running moto server classes.

    Every attach point is guarded on its own: an op already present on
    GlueResponse (ours from a previous call, or shipped by a newer moto)
    is left alone, and a patch already wrapping its target is not wrapped
    twice — partial upstream adoption can never silence the rest.
    """
    for operation, handler in _RESPONSE_OPERATIONS.items():
        if getattr(GlueResponse, operation, None) is None:
            setattr(GlueResponse, operation, handler)
    for owner, attribute, replacement in _PATCHES:
        if getattr(owner, attribute, None) is not replacement:
            setattr(owner, attribute, replacement)
