Feature: Pipeline command dispatch
  `python -m nyc_taxi_demand_forecasting.interfaces.cli <command> --config <path>`
  maps each subcommand to a registered pipeline runner. These pipelines are
  real, so routing identity is pinned through per-command recording runners
  while the registry dict itself stays production; `collect` also runs
  end-to-end against a fake HTTP seam. Config-level and dispatch-level
  failures exit as one named line, never a traceback.

  Scenario Outline: A subcommand dispatches its own pipeline runner
    Given every pipeline's runner records its calls
    When I run the pipeline command "<command>"
    Then only the "<command>" pipeline ran once
    And stderr shows "pipeline_command_completed"

    Examples:
      | command    |
      | collect    |
      | preprocess |
      | features   |
      | train      |
      | tune       |
      | evaluate   |
      | deploy     |
      | monitor    |

  Scenario: Collect downloads the configured month
    Given a valid project config exists
    And the TLC endpoint serves parquet bytes
    When I run the pipeline command "collect"
    Then the raw parquet for month "2023-01" exists
    And the collector fetched "https://example.test/yellow_tripdata_2023-01.parquet"
    And stderr shows "pipeline_command_completed"

  Scenario: A missing config exits naming the path
    Given no project config exists
    When I run the pipeline command "collect"
    Then the command exits reporting the missing config path
    And stderr shows "pipeline_command_failed"
    And the failure log names "collect"
    And stderr does not show "pipeline_command_completed"

  Scenario: An unknown command is rejected before dispatch
    When I run the pipeline command "bogus"
    Then the command exits with code 2
    And stderr shows "invalid choice"
