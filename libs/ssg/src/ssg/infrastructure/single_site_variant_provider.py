from ssg.application.ports.site_variant_provider import SiteVariantProvider
from ssg.domain import BuildContext, Site, SiteVariant


class SingleSiteVariantProvider(SiteVariantProvider):
    def variants(
        self, site: Site, context: BuildContext
    ) -> tuple[SiteVariant, ...]:
        return (SiteVariant(site=site, output_path=context.output_path),)
