from _concept_components import ConceptStep, FlowDiagramScene


class CrispDmScene(FlowDiagramScene):
    title = "CRISP-DM"
    subtitle = "A practical loop for data mining projects"
    steps = (
        ConceptStep("Business", "define the goal"),
        ConceptStep("Data", "understand sources"),
        ConceptStep("Prepare", "clean and shape"),
        ConceptStep("Model", "train candidates"),
        ConceptStep("Evaluate", "check usefulness"),
        ConceptStep("Deploy", "deliver value"),
    )
