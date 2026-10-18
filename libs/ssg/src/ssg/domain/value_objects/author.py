from dataclasses import dataclass


@dataclass(frozen=True)
class Author:
    """One named byline on a dated post.

    A frozen value object (not a mapping) so `Page`, which carries authors,
    stays hashable: the dependency tracker keys pages in sets. `url` is
    optional; templates fall back to the plain name when it is empty.
    """

    name: str
    url: str = ""
