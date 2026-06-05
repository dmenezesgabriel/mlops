from __future__ import annotations

from videos.concepts.base import ConceptExtension
from videos.core.domain.concept import Concept, ConceptId, ConceptMetadata, ConceptTitle
from videos.core.domain.narrative import Beat, BeatKind, NarrationLine, Narrative


class MlopsLifecycleExtension(ConceptExtension):
    @property
    def concept(self) -> Concept:
        return Concept(
            id=ConceptId("mlops_lifecycle"),
            metadata=ConceptMetadata(
                title=ConceptTitle(
                    short="MLOps Lifecycle",
                    subtitle="From data to production and back",
                ),
                description="Continuous Delivery for Machine Learning lifecycle based on CD4ML",
                tags=("mlops", "lifecycle", "cd4ml", "ml engineering"),
            ),
        )

    def create_narrative(self) -> Narrative:
        return Narrative(
            self.concept,
            (
                Beat(
                    BeatKind.OPENING,
                    NarrationLine(
                        "MLOps Lifecycle. "
                        "Building a model is just the beginning. "
                        "The real challenge is keeping it running and improving it.",
                        6.0,
                    ),
                    "title",
                    {},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Machine learning changes on 3 axes. "
                        "Code, Data, and Model. "
                        "Traditional DevOps only handles one of these.",
                        6.0,
                    ),
                    "three_axes",
                    {},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Data Collection. Version your data like you version your code.",
                        5.0,
                    ),
                    "phase_collect",
                    {"color": "#4A90D9", "label": "Collect"},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Feature Engineering. "
                        "Turn raw data into signals. "
                        "Store features for reuse between training and serving.",
                        5.0,
                    ),
                    "phase_features",
                    {"color": "#50C878", "label": "Features"},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Training. Track every experiment. If you didn't log it, it didn't happen.",
                        6.0,
                    ),
                    "phase_train",
                    {"color": "#FF8C42", "label": "Train"},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Model Registration. "
                        "Promote the good ones, archive the rest. "
                        "Governance matters.",
                        5.0,
                    ),
                    "phase_register",
                    {"color": "#9B59B6", "label": "Register"},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Deployment. Ship safely. "
                        "Your model deserves the same care as any software.",
                        6.0,
                    ),
                    "phase_deploy",
                    {"color": "#E74C3C", "label": "Deploy"},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Monitoring. Watch for data drift, concept drift, performance degradation.",
                        6.0,
                    ),
                    "phase_monitor",
                    {"color": "#00B5B8", "label": "Monitor"},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Why MLOps? Because ML breaks in production. "
                        "Data pipelines fail. Models drift. "
                        "Without MLOps, you are flying blind.",
                        7.0,
                    ),
                    "why_mlops",
                    {},
                ),
                Beat(
                    BeatKind.EMPHASIS,
                    NarrationLine(
                        "The feedback loop. "
                        "Production data feeds back into training. "
                        "Your next model learns from the last one's mistakes.",
                        7.0,
                    ),
                    "feedback",
                    {},
                ),
                Beat(
                    BeatKind.REVEAL,
                    NarrationLine(
                        "Continuous improvement. "
                        "Predictions become labeled data through monitoring. "
                        "That data trains the next version. The loop never stops.",
                        6.0,
                    ),
                    "continuous",
                    {},
                ),
                Beat(
                    BeatKind.RECAP,
                    NarrationLine(
                        "Data to production and back. That is the MLOps lifecycle.",
                        4.0,
                    ),
                    "recap",
                    {},
                ),
            ),
        )
