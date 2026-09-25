Feature: Managed-results workgroups

  A workgroup with ManagedQueryResultsConfiguration.Enabled=true owns its
  query results in Athena-managed storage: the canonical model forbids an
  OutputLocation on such a workgroup, and awswrangler's managed path
  (awswrangler/athena/_utils.py:105-109) therefore sends StartQueryExecution
  without any ResultConfiguration, then reads the rows inline via
  GetQueryResults (awswrangler/athena/_read.py:450). The emulator accepts
  that request, stores an empty ResultConfiguration, skips S3 artifacts
  (ADR-0011), and answers GetQueryExecution with no OutputLocation — the
  exact shape wrangler's managed tests assert
  (awswrangler/tests/unit/test_athena.py:125).

  Background:
    Given a managed-results query harness

  Scenario: managed workgroup runs a query without an output location
    Given a workgroup named "managed" with managed query results enabled
    When StartQueryExecution runs SELECT 1 on it without an output location
    Then the execution succeeds and the writer was not called
    And GetQueryExecution reports ResultConfiguration without OutputLocation
    And GetQueryResults serves the inline rows