Feature: Render a diagram from a YAML definition

  `diagrams-cli` loads a diagram definition from `<definitions-dir>/<id>.yaml`,
  renders it through mingrammer's `diagrams` package, and writes
  `<output-dir>/<filename>.png`. Load and render failures print the error to
  stderr and exit 1.

  Scenario: A valid definition renders a PNG artifact
    Given a definitions directory with a valid diagram "mlops_lifecycle"
    When I run "diagrams-cli" for "mlops_lifecycle"
    Then the command exits with code 0
    And the artifact "mlops_lifecycle.png" exists in the output directory
    And the diagram records the edge from "Raw Data" to "Model" labeled "trains"

  Scenario: A missing definition exits with an error
    When I run "diagrams-cli" for "nonexistent_diagram"
    Then the command exits with code 1
    And stderr shows "Missing diagram definition"

  Scenario: A malformed definition exits with an error
    Given a definitions directory with a malformed diagram "bad_diagram"
    When I run "diagrams-cli" for "bad_diagram"
    Then the command exits with code 1
    And stderr shows "expected list"
