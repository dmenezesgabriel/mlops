Feature: Engine versions

  ListEngineVersions answers with the emulator's pinned engine list: a single
  entry (AUTO / Athena engine version 3), matching the workgroup default
  engine the Trino-backed query engine represents.

  Scenario: ListEngineVersions returns the pinned engine
    When ListEngineVersions is called
    Then the response contains 1 engine version
    And the engine is "AUTO" with effective version "Athena engine version 3"
    And no NextToken is returned