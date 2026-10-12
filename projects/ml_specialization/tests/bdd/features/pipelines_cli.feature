Feature: Pipeline command dispatch
  `python -m ml_specialization.interfaces.cli <command> --config <path>`
  maps each subcommand to a registered pipeline runner. All eight
  pipelines are specialization stubs — each loads the config, then raises
  its named NotImplementedError, which `main()` turns into a clean
  one-line exit instead of a traceback.

  Scenario Outline: A stub pipeline exits reporting its own name
    Given a valid project config exists
    When I run the pipeline command "<command>"
    Then the command exits reporting "<command> pipeline is not implemented"
    And stderr shows "pipeline_command_failed"
    And the failure log names "<command>"
    And stderr does not show "pipeline_command_completed"

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

  Scenario: A missing config exits naming the path
    Given no project config exists
    When I run the pipeline command "collect"
    Then the command exits reporting the missing config path
    And stderr shows "pipeline_command_failed"
    And the failure log names "collect"

  Scenario: An unknown command is rejected before dispatch
    When I run the pipeline command "bogus"
    Then the command exits with code 2
    And stderr shows "invalid choice"
