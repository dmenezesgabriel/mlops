Feature: Workgroup control plane

  The five workgroup operations follow the canonical Athena service model:
  CreateWorkGroup, GetWorkGroup, ListWorkGroups, UpdateWorkGroup, DeleteWorkGroup.
  The "primary" workgroup is pre-seeded like moto
  (research_repos/moto/moto/athena/models.py:263-269) but, unlike moto, cannot
  be deleted — the AWS document behavior is "The primary workgroup cannot be
  deleted."

  Background:
    Given a fresh workgroup registry

  Scenario: CreateWorkGroup then GetWorkGroup round-trips the configuration
    When a workgroup named "analytics" is created with an output location
    Then GetWorkGroup returns the same output location
    And the workgroup state is ENABLED

  Scenario: Duplicate CreateWorkGroup is rejected
    When a workgroup named "analytics" is created
    And a second CreateWorkGroup reuses the name "analytics"
    Then CreateWorkGroup answers InvalidRequestException with HTTP 400

  Scenario: The pre-seeded primary workgroup cannot be deleted
    Given the emulator boots with a "primary" workgroup
    When DeleteWorkGroup targets "primary"
    Then DeleteWorkGroup answers InvalidRequestException naming "primary"

  Scenario: UpdateWorkGroup merges a partial configuration update
    When a workgroup named "analytics" is created with an output location
    And UpdateWorkGroup disables "analytics" without touching the configuration
    Then GetWorkGroup returns the output location and state "DISABLED"