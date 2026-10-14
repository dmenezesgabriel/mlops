from collections.abc import Callable
from datetime import date
from typing import cast

from babel.dates import format_date as babel_format_date
from jinja2 import Environment, PackageLoader, StrictUndefined


def _format_date(value: date, locale: str) -> str:
    # BCP-47 "pt-BR" → babel's "pt_BR" spelling.
    return babel_format_date(value, "medium", locale.replace("-", "_"))


def create_frontend_environment() -> Environment:
    # autoescape=True: the safe setup this Flask audit rule asks for
    environment = Environment(  # nosemgrep: python.flask.security.xss.audit.direct-use-of-jinja2.direct-use-of-jinja2
        autoescape=True,
        loader=PackageLoader("ssg.infrastructure.frontend", "templates"),
        undefined=StrictUndefined,
    )
    # jinja types `filters` as the union of its builtin filter signatures;
    # a custom (value, locale) filter needs the cast to register.
    environment.filters["format_date"] = cast(Callable[..., str], _format_date)
    return environment
