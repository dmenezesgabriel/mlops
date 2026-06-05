from videos.production._components import VisualComponent


class TestVisualComponent:
    def test_stores_fields(self) -> None:
        c = VisualComponent(component_id="c1", description="A title text")
        assert c.component_id == "c1"
        assert c.description == "A title text"
