from __future__ import annotations

from videos.application.component_factory import ComponentFactory
from videos.domain.layout import LayoutRegion, LayoutSpec
from videos.domain.narrative import Narrative
from videos.domain.scene_spec import SceneSpec, VisualObject
from videos.domain.storyboard import Storyboard
from videos.domain.style import StyleSpec
from videos.domain.timeline import TimelineEvent, TimelineSpec


class StoryboardPlanner:
    def __init__(
        self, component_factory: ComponentFactory | None = None
    ) -> None:
        self._component_factory = component_factory or ComponentFactory()

    def plan(self, narrative: Narrative) -> Storyboard:
        scenes: list[SceneSpec] = []
        for index, beat in enumerate(narrative.beats):
            scene_id = f"{narrative.concept.id.value}_beat_{index}"
            region_names = {"title", "body", "diagram"}
            regions = tuple(
                LayoutRegion(r)
                for r in region_names
                if r in LayoutRegion.all_region_names()
            )

            visual_objects = (
                VisualObject(
                    object_id=f"{scene_id}_title",
                    region="title",
                    semantic_purpose=f"Display {beat.kind.value} text",
                ),
                VisualObject(
                    object_id=f"{scene_id}_body",
                    region="body",
                    semantic_purpose=f"Display narration for {beat.visual_key}",
                ),
            )

            components = self._component_factory.create_components(beat)

            timeline_events = (
                TimelineEvent(
                    time_seconds=0.0,
                    action="appear",
                    target_object_id=f"{scene_id}_title",
                ),
                TimelineEvent(
                    time_seconds=0.5,
                    action="appear",
                    target_object_id=f"{scene_id}_body",
                ),
            )

            scene = SceneSpec(
                scene_id=scene_id,
                title=beat.visual_key.replace("_", " ").title(),
                goal=beat.narration.text[:80],
                duration_seconds=beat.narration.duration_seconds,
                layout=LayoutSpec(regions=regions),
                visual_objects=visual_objects,
                timeline=TimelineSpec(events=timeline_events),
                style=StyleSpec(),
                components=tuple(components),
            )
            scenes.append(scene)

        return Storyboard(scenes=scenes)
