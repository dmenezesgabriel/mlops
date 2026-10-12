Feature: Monitor pipeline report
  `monitor --config <path>` loads the champion model, scores a simulated
  production frame, and writes `reports/monitoring.md`. The scenarios
  drive the real CLI argv → registry → run → report-file loop the manual
  recipe exercises; only the MLflow registry/model boundary is faked.

  Scenario: The monitor writes a report for the champion model
    Given a monitor project config exists
    And a training dataset exists
    And the registry promotes champion version "2" of "model"
    When I run the monitor pipeline
    Then the monitoring report exists
    And the report names champion version "2" with alias "@champion"
    And the report marks "Drift Detected"
    And the monitor run logged "pipeline_command_completed"

  Scenario: An empty model registry exits naming the model
    Given a monitor project config exists
    And a training dataset exists
    And the registry holds no versions of "model"
    When I run the monitor pipeline
    Then the monitor run exits reporting "No registered model found"
    And the monitor run logged "pipeline_command_failed"
    And the monitor run did not log "pipeline_command_completed"
    And no monitoring report exists
