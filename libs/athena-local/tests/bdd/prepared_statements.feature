Feature: Prepared statement control plane

  The six prepared statement operations follow the canonical Athena service model:
  CreatePreparedStatement, GetPreparedStatement, ListPreparedStatements,
  UpdatePreparedStatement, DeletePreparedStatement, BatchGetPreparedStatement.
  Statements are scoped to workgroups and use user-provided names as keys
  (service model PreparedStatement shape). The default workgroup is "primary"
  when not specified. GetPreparedStatement raises ResourceNotFoundException for
  missing statements per awswrangler expectations
  (research_repos/aws-sdk-pandas/awswrangler/athena/_statements.py:26-29).

  Background:
    Given a fresh prepared statement registry

  Scenario: CreatePreparedStatement then GetPreparedStatement round-trips the statement
    When a prepared statement named "flights_stmt" is created
    Then GetPreparedStatement returns the statement details
    And the statement is scoped to the "primary" workgroup

  Scenario: CreatePreparedStatement in a custom workgroup
    When a prepared statement named "analytics_stmt" is created in the "analytics" workgroup
    Then GetPreparedStatement returns the statement with workgroup "analytics"
    And ListPreparedStatements for "analytics" includes the statement

  Scenario: GetPreparedStatement for a missing statement is rejected
    When GetPreparedStatement targets a non-existent statement in "primary"
    Then GetPreparedStatement answers ResourceNotFoundException

  Scenario: ListPreparedStatements with pagination
    When 5 prepared statements are created in the "analytics" workgroup
    And ListPreparedStatements requests MaxResults 2
    Then the response contains 2 statements
    And a NextToken is returned
    When ListPreparedStatements requests MaxResults 2 with the NextToken
    Then the response contains 2 more statements
    And a NextToken is returned
    When ListPreparedStatements requests MaxResults 2 with the NextToken
    Then the response contains 1 statement
    And no NextToken is returned

  Scenario: UpdatePreparedStatement modifies the statement
    When a prepared statement named "to_update" is created
    And UpdatePreparedStatement modifies the query and description
    Then GetPreparedStatement returns the updated query and description
    And LastModifiedTime has increased

  Scenario: DeletePreparedStatement removes the statement
    When a prepared statement named "to_delete" is created
    And DeletePreparedStatement targets the created statement in "primary"
    Then GetPreparedStatement for the deleted statement answers ResourceNotFoundException
    And ListPreparedStatements no longer includes the statement

  Scenario: BatchGetPreparedStatement returns multiple statements
    Given 2 prepared statements are created
    When BatchGetPreparedStatement requests both statement names
    Then the response contains both PreparedStatement objects
    And no UnprocessedPreparedStatementNames are returned

  Scenario: BatchGetPreparedStatement with missing names
    Given 1 prepared statements are created
    When BatchGetPreparedStatement requests the created name and 2 missing names
    Then the response contains 1 PreparedStatement object
    And 2 UnprocessedPreparedStatementNames are returned
