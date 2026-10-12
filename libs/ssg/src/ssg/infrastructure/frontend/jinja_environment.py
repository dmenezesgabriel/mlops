from jinja2 import Environment, PackageLoader, StrictUndefined


def create_frontend_environment() -> Environment:
    # autoescape=True: the safe setup this Flask audit rule asks for
    return Environment(  # nosemgrep: python.flask.security.xss.audit.direct-use-of-jinja2.direct-use-of-jinja2
        autoescape=True,
        loader=PackageLoader("ssg.infrastructure.frontend", "templates"),
        undefined=StrictUndefined,
    )
