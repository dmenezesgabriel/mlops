from _concept_components import ConceptStep, FlowDiagramScene


class MlopsLifecycleScene(FlowDiagramScene):
    title = "MLOps Lifecycle"
    subtitle = "From data to monitored model behavior"
    steps = (
        ConceptStep("Collect", "version data"),
        ConceptStep("Features", "serve signals"),
        ConceptStep("Train", "track runs"),
        ConceptStep("Register", "promote models"),
        ConceptStep("Deploy", "ship safely"),
        ConceptStep("Monitor", "detect drift"),
    )
