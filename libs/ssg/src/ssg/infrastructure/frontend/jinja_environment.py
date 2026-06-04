from jinja2 import DictLoader, Environment, StrictUndefined

from ssg.infrastructure.frontend.templates import INDEX_TEMPLATE, PAGE_TEMPLATE, TEMPLATE_PARTS


def create_frontend_environment() -> Environment:
    return Environment(
        autoescape=True,
        loader=DictLoader(
            {
                "index.html": INDEX_TEMPLATE,
                "page.html": PAGE_TEMPLATE,
                "parts.html": TEMPLATE_PARTS,
            }
        ),
        undefined=StrictUndefined,
    )
