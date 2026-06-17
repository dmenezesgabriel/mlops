# Backward-compatible re-export — import from canonical location instead.
from videos.domain.value_objects.brand import DEFAULT_BRAND, BrandColors

__all__ = ["BrandColors", "DEFAULT_BRAND"]
