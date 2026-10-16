from dataclasses import dataclass


@dataclass(frozen=True)
class SocialCard:
    """Text content for one generated og:image card.

    `eyebrow` is the small overline above the title (the collection title
    for pages, empty for the index card); `description` and `site_title`
    render in the footer band. `locale` identifies the emitting variant so
    a renderer can pick locale-appropriate type treatment.
    """

    site_title: str
    eyebrow: str
    title: str
    description: str
    locale: str
