class TestImportBoundaries:
    def test_core_domain_does_not_import_manim(self) -> None:
        import videos.domain.concept
        import videos.domain.layout
        import videos.domain.narrative
        import videos.domain.quality
        import videos.domain.scene_spec
        import videos.domain.storyboard
        import videos.domain.style
        import videos.domain.timeline

        mods = [
            videos.domain.concept,
            videos.domain.narrative,
            videos.domain.storyboard,
            videos.domain.scene_spec,
            videos.domain.layout,
            videos.domain.timeline,
            videos.domain.style,
            videos.domain.quality,
        ]
        for mod in mods:
            src = getattr(mod, "__file__", "") or ""
            with open(src) as f:
                content = f.read()
            assert "manim" not in content.lower(), f"{src} imports manim"

    def test_core_application_does_not_import_manim(self) -> None:
        import videos.application.director
        import videos.application.quality_gate
        import videos.application.render_pipeline
        import videos.application.storyboard_planner

        mods = [
            videos.application.director,
            videos.application.storyboard_planner,
            videos.application.quality_gate,
            videos.application.render_pipeline,
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
