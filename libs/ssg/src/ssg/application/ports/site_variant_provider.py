from typing import Protocol

from ssg.domain import BuildContext, Site, SiteVariant


class SiteVariantProvider(Protocol):
    def variants(
        self, site: Site, context: BuildContext
    ) -> tuple[SiteVariant, ...]: ...
