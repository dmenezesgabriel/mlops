from typing import Protocol, runtime_checkable

from ssg.domain import BuildContext, Site, SiteVariant


@runtime_checkable
class SiteVariantProvider(Protocol):
    def variants(
        self, site: Site, context: BuildContext
    ) -> tuple[SiteVariant, ...]: ...
