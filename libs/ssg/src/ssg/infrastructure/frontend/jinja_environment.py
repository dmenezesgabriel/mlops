from jinja2 import Environment, PackageLoader, StrictUndefined


def create_frontend_environment() -> Environment:
    return Environment(
        autoescape=True,
        loader=PackageLoader("ssg.infrastructure.frontend", "templates"),
        undefined=StrictUndefined,
    )
