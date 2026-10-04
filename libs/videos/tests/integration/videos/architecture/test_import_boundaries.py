class TestImportBoundaries:
    def test_core_domain_does_not_import_manim(self) -> None:
        import videos.domain.entities.concept
        import videos.domain.entities.narrative
        import videos.domain.entities.storyboard
        import videos.domain.value_objects.layout
        import videos.domain.value_objects.quality
        import videos.domain.value_objects.scene_spec
        import videos.domain.value_objects.style
        import videos.domain.value_objects.timeline

        mods = [
            videos.domain.entities.concept,
            videos.domain.entities.narrative,
            videos.domain.entities.storyboard,
            videos.domain.value_objects.scene_spec,
            videos.domain.value_objects.layout,
            videos.domain.value_objects.timeline,
            videos.domain.value_objects.style,
            videos.domain.value_objects.quality,
        ]
        for mod in mods:
            src = getattr(mod, "__file__", "") or ""
            with open(src) as f:
                content = f.read()
            assert "manim" not in content.lower(), f"{src} imports manim"

    def test_core_application_does_not_import_manim(self) -> None:
        import videos.application.director
        import videos.application.storyboard_planner
        import videos.application.use_cases.quality_gate

        mods = [
            videos.application.director,
            videos.application.storyboard_planner,
            videos.application.use_cases.quality_gate,
        ]
        for mod in mods:
            src = getattr(mod, "__file__", "") or ""
            with open(src) as f:
                content = f.read()
            assert "manim" not in content.lower(), f"{src} imports manim"

    def test_validation_does_not_import_manim(self) -> None:
        import videos.domain.validation.layout_rules
        import videos.domain.validation.scene_rules
        import videos.domain.validation.text_rules
        import videos.domain.validation.timeline_rules

        mods = [
            videos.domain.validation.text_rules,
            videos.domain.validation.layout_rules,
            videos.domain.validation.timeline_rules,
            videos.domain.validation.scene_rules,
        ]
        for mod in mods:
            src = getattr(mod, "__file__", "") or ""
            with open(src) as f:
                content = f.read()
            assert "manim" not in content.lower(), f"{src} imports manim"
