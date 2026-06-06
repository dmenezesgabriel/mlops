class TestDependencyDirection:
    def test_core_domain_does_not_import_adapters(self) -> None:
        import videos.core.domain.concept
        import videos.core.domain.layout
        import videos.core.domain.narrative
        import videos.core.domain.quality
        import videos.core.domain.scene_spec
        import videos.core.domain.storyboard
        import videos.core.domain.style
        import videos.core.domain.timeline

        mods = [
            videos.core.domain.concept,
            videos.core.domain.narrative,
            videos.core.domain.storyboard,
            videos.core.domain.scene_spec,
            videos.core.domain.layout,
            videos.core.domain.timeline,
            videos.core.domain.style,
            videos.core.domain.quality,
        ]
        for mod in mods:
            src = getattr(mod, "__file__", "") or ""
            with open(src) as f:
                content = f.read()
            assert (
                "adapters" not in content.lower()
            ), f"{src} imports from adapters"

    def test_core_application_does_not_import_adapters(self) -> None:
        import videos.core.application.director
        import videos.core.application.quality_gate
        import videos.core.application.render_pipeline
        import videos.core.application.storyboard_planner

        mods = [
            videos.core.application.director,
            videos.core.application.storyboard_planner,
            videos.core.application.quality_gate,
            videos.core.application.render_pipeline,
        ]
        for mod in mods:
            src = getattr(mod, "__file__", "") or ""
            with open(src) as f:
                content = f.read()
            assert (
                "adapters" not in content.lower()
            ), f"{src} imports from adapters"

    def test_validation_does_not_import_adapters(self) -> None:
        import videos.validation.layout_rules
        import videos.validation.scene_rules
        import videos.validation.text_rules
        import videos.validation.timeline_rules

        mods = [
            videos.validation.text_rules,
            videos.validation.layout_rules,
            videos.validation.timeline_rules,
            videos.validation.scene_rules,
        ]
        for mod in mods:
            src = getattr(mod, "__file__", "") or ""
            with open(src) as f:
                content = f.read()
            assert (
                "adapters" not in content.lower()
            ), f"{src} imports from adapters"
