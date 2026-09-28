import importlib
from types import ModuleType


def _module_source(mod: ModuleType) -> tuple[str, str]:
    src = getattr(mod, "__file__", "") or ""
    with open(src) as f:
        return src, f.read()


def _assert_no_layer_imports(
    module_names: list[str], forbidden: tuple[str, ...]
) -> None:
    for name in module_names:
        src, content = _module_source(importlib.import_module(name))
        for layer in forbidden:
            assert layer not in content.lower(), f"{src} imports from {layer}"


class TestDependencyDirection:
    def test_domain_is_independent(self) -> None:
        # Domain must not import application, infrastructure, or presentation
        _assert_no_layer_imports(
            [
                "videos.domain.concept",
                "videos.domain.narrative",
                "videos.domain.storyboard",
                "videos.domain.scene_spec",
                "videos.domain.layout",
                "videos.domain.timeline",
                "videos.domain.style",
                "videos.domain.quality",
            ],
            ("infrastructure", "presentation", "application"),
        )

    def test_application_does_not_import_adapters_or_presentation(
        self,
    ) -> None:
        # Application must not import infrastructure or presentation
        _assert_no_layer_imports(
            [
                "videos.application.director",
                "videos.application.storyboard_planner",
                "videos.application.quality_gate",
                "videos.application.render_pipeline",
            ],
            ("infrastructure", "presentation"),
        )

    def test_domain_validation_does_not_import_adapters_or_presentation(
        self,
    ) -> None:
        # Domain validation must not import infrastructure, presentation,
        # or application
        _assert_no_layer_imports(
            [
                "videos.domain.validation.text_rules",
                "videos.domain.validation.layout_rules",
                "videos.domain.validation.timeline_rules",
                "videos.domain.validation.scene_rules",
            ],
            ("infrastructure", "presentation", "application"),
        )
