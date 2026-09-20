"""In-memory data catalog registry (ADR-0003) — fresh module per responsibility.

The Athena ``DataCatalog`` shape lives outside the Glue backend: registering a
catalog only records name, type, description, and parameters (moto
``research_repos/moto/moto/athena/models.py:90-111``). Every AWS account has a
pre-registered Glue-backed ``AwsDataCatalog``; the CLI ``list-data-catalogs``
example shows it in the listing without any registration, so the seed mirrors
real AWS rather than moto (which starts ``data_catalogs`` empty).

Missing catalogs raise ``InvalidRequestException``: the service-2.json declares
no ``ResourceNotFoundException`` for the five data catalog operations.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from athena_local.errors import InvalidRequestException
from athena_local.schemas import Tag

AWS_DATA_CATALOG_NAME = "AwsDataCatalog"


def missing_catalog_error(name: str) -> InvalidRequestException:
    return InvalidRequestException(f"DataCatalog {name} does not exist")


@dataclass
class DataCatalogRecord:
    """A registered data catalog; wire shapes built by the payload methods."""

    name: str
    catalog_type: str
    description: str | None = None
    parameters: dict[str, str] = field(default_factory=dict)
    tags: list[Tag] = field(default_factory=list)

    def to_payload(self) -> dict[str, object]:
        """Serialize to the GetDataCatalog ``DataCatalog`` wire shape."""
        payload: dict[str, object] = {
            "Name": self.name,
            "Type": self.catalog_type,
        }
        if self.description is not None:
            payload["Description"] = self.description
        if self.parameters:
            payload["Parameters"] = dict(self.parameters)
        return payload

    def to_summary_payload(self) -> dict[str, object]:
        """Serialize to the ListDataCatalogs ``DataCatalogSummary`` wire shape."""
        return {"CatalogName": self.name, "Type": self.catalog_type}


@dataclass
class DataCatalogStore:
    """In-memory data catalog registry; single-process, race-free (ADR-0003)."""

    by_name: dict[str, DataCatalogRecord] = field(
        default_factory=dict, init=False
    )

    def __post_init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Drop every catalog and re-seed ``AwsDataCatalog`` (test reset)."""
        self.by_name = {
            AWS_DATA_CATALOG_NAME: DataCatalogRecord(
                name=AWS_DATA_CATALOG_NAME, catalog_type="GLUE"
            )
        }

    def create(
        self,
        name: str,
        catalog_type: str,
        description: str | None,
        parameters: dict[str, str],
    ) -> DataCatalogRecord:
        if name in self.by_name:
            raise InvalidRequestException(f"DataCatalog {name} already exists")
        record = DataCatalogRecord(
            name=name,
            catalog_type=catalog_type,
            description=description,
            parameters=parameters,
        )
        self.by_name[name] = record
        return record

    def get(self, name: str) -> DataCatalogRecord:
        if name not in self.by_name:
            raise missing_catalog_error(name)
        return self.by_name[name]

    def list(
        self,
        max_results: int | None = None,
        next_token: str | None = None,
    ) -> tuple[list[DataCatalogRecord], str | None]:
        """Return catalogs with pagination.

        Returns a tuple of (records, next_token). ``next_token`` is None when
        there are no more results.
        """
        all_records = list(self.by_name.values())
        start_index = 0
        if next_token is not None:
            try:
                start_index = int(next_token)
            except ValueError:
                raise InvalidRequestException(
                    f"Invalid NextToken: {next_token}"
                ) from None
        if start_index >= len(all_records):
            return [], None
        end_index = len(all_records)
        if max_results is not None and max_results > 0:
            end_index = min(start_index + max_results, len(all_records))
        page_records = all_records[start_index:end_index]
        next_token_out = (
            str(end_index) if end_index < len(all_records) else None
        )
        return page_records, next_token_out

    def update(
        self,
        name: str,
        catalog_type: str,
        description: str | None,
        parameters: dict[str, str] | None,
    ) -> DataCatalogRecord:
        record = self.get(name)
        record.catalog_type = catalog_type
        if description is not None:
            record.description = description
        if parameters is not None:
            record.parameters = parameters
        return record

    def delete(self, name: str) -> DataCatalogRecord:
        record = self.get(name)
        del self.by_name[name]
        return record
