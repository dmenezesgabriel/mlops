from videos.production.brand import DEFAULT_BRAND, BrandColors


class TestBrandColors:
    def test_default_primary(self) -> None:
        assert DEFAULT_BRAND.primary == "#4A90D9"

    def test_default_background(self) -> None:
        assert DEFAULT_BRAND.background == "#1e1e1e"

    def test_custom_brand(self) -> None:
        brand = BrandColors(primary="#FF0000", background="#FFFFFF")
        assert brand.primary == "#FF0000"
        assert brand.background == "#FFFFFF"
