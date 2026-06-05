class TestDependencyDirection:
    def test_core_domain_does_not_import_adapters(self) -> None:
        import videos.core.domain._concept
        import videos.core.domain._layout
        import videos.core.domain._narrative
        import videos.core.domain._quality
        import videos.core.domain._scene_spec
        import videos.core.domain._storyboard
        import videos.core.domain._style
        import videos.core.domain._timeline

        mods = [
            videos.core.domain._concept,
            videos.core.domain._narrative,
            videos.core.domain._storyboard,
            videos.core.domain._scene_spec,
            videos.core.domain._layout,
            videos.core.domain._timeline,
            videos.core.domain._style,
            videos.core.domain._quality,
        ]
        for mod in mods:
            src = getattr(mod, "__file__", "") or ""
            with open(src) as f:
                content = f.read()
            assert "adapters" not in content.lower(), f"{src} imports from adapters"

    def test_core_application_does_not_import_adapters(self) -> None:
        import videos.core.application._director
        import videos.core.application._quality_gate
        import videos.core.application._render_pipeline
        import videos.core.application._scene_compiler
        import videos.core.application._storyboard_planner

        mods = [
            videos.core.application._director,
            videos.core.application._storyboard_planner,
            videos.core.application._scene_compiler,
            videos.core.application._quality_gate,
            videos.core.application._render_pipeline,
        ]
        for mod in mods:
            src = getattr(mod, "__file__", "") or ""
            with open(src) as f:
                content = f.read()
            assert "adapters" not in content.lower(), f"{src} imports from adapters"

    def test_validation_does_not_import_adapters(self) -> None:
        import videos.validation._layout_rules
        import videos.validation._scene_rules
        import videos.validation._text_rules
        import videos.validation._timeline_rules

        mods = [
            videos.validation._text_rules,
            videos.validation._layout_rules,
            videos.validation._timeline_rules,
            videos.validation._scene_rules,
        ]
        for mod in mods:
            src = getattr(mod, "__file__", "") or ""
            with open(src) as f:
                content = f.read()
            assert "adapters" not in content.lower(), f"{src} imports from adapters"

    def test_concepts_do_not_import_adapters(self) -> None:
        import videos.concepts.bias_variance_tradeoff
        import videos.concepts.crisp_dm
        import videos.concepts.mlops_lifecycle
        import videos.concepts.underfit_vs_overfit

        for mod in (
            videos.concepts.bias_variance_tradeoff,
            videos.concepts.crisp_dm,
            videos.concepts.mlops_lifecycle,
            videos.concepts.underfit_vs_overfit,
        ):
            src = getattr(mod, "__file__", "") or ""
            with open(src) as f:
                content = f.read()
            assert "adapters" not in content, f"{src} imports from adapters"
