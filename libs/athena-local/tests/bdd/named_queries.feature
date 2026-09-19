Feature: Named query control plane

  The five named query operations follow the canonical Athena service model:
  CreateNamedQuery, GetNamedQuery, ListNamedQueries, DeleteNamedQuery,
  BatchGetNamedQuery. Queries are scoped to workgroups and use UUID4 IDs
  (moto research_repos/moto/moto/athena/models.py:193-207). The default
  workgroup is "primary" when not specified.

  Background:
    Given a fresh named query registry

  Scenario: CreateNamedQuery then GetNamedQuery round-trips the query
    When a named query named "flights_query" is created
    Then GetNamedQuery returns the query details
    And the query is scoped to the "primary" workgroup

  Scenario: CreateNamedQuery in a custom workgroup
    When a named query named "analytics_query" is created in the "analytics" workgroup
    Then GetNamedQuery returns the query with workgroup "analytics"
    And ListNamedQueries for "analytics" includes the query ID

  Scenario: GetNamedQuery for a missing ID is rejected
    When GetNamedQuery targets a non-existent query ID
    Then GetNamedQuery answers InvalidRequestException

  Scenario: ListNamedQueries with pagination
    When 5 named queries are created in the "analytics" workgroup
    And ListNamedQueries requests MaxResults 2
    Then the response contains 2 query IDs
    And a NextToken is returned
    When ListNamedQueries requests MaxResults 2 with the NextToken
    Then the response contains 2 more query IDs
    And a NextToken is returned
    When ListNamedQueries requests MaxResults 2 with the NextToken
    Then the response contains 1 query ID
    And no NextToken is returned

  Scenario: DeleteNamedQuery removes the query
    When a named query named "to_delete" is created
    And DeleteNamedQuery targets the created query ID
    Then GetNamedQuery for the deleted ID answers InvalidRequestException
    And ListNamedQueries no longer includes the query ID

  Scenario: BatchGetNamedQuery returns multiple queries
    Given 2 named queries are created
    When BatchGetNamedQuery requests both query IDs
    Then the response contains both NamedQuery objects
    And no UnprocessedNamedQueryIds are returned

  Scenario: BatchGetNamedQuery with missing IDs
    Given 1 named queries are created
    When BatchGetNamedQuery requests the created ID and 2 missing IDs
    Then the response contains 1 NamedQuery object
    And 2 UnprocessedNamedQueryIds are returned
