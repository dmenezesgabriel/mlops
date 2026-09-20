Feature: Data catalog control plane

  The five data catalog operations follow the canonical Athena service model:
  CreateDataCatalog, GetDataCatalog, ListDataCatalogs, UpdateDataCatalog,
  DeleteDataCatalog. ``AwsDataCatalog`` is pre-registered as a GLUE catalog.
  LAMBDA catalogs get function-derived metadata-function and record-function
  parameters on registration (the documented get-data-catalog.rst output).

  Background:
    Given a fresh data catalog registry

  Scenario: CreateDataCatalog then GetDataCatalog round-trips the catalog
    When a GLUE data catalog named "glue_catalog" is created
    Then GetDataCatalog returns the catalog with type "GLUE"

  Scenario: The default AwsDataCatalog is pre-registered
    Given the pre-registered AwsDataCatalog
    When GetDataCatalog targets the seeded catalog
    Then the catalog type is "GLUE"
    And ListDataCatalogs includes the seeded catalog

  Scenario: CreateDataCatalog normalizes LAMBDA parameters
    When a LAMBDA data catalog named "dynamo_db_catalog" is created with function "arn:aws:lambda:us-west-2:1:function:dynamo_db_lambda"
    Then GetDataCatalog returns catalog-, metadata-function-, and record-function parameters

  Scenario: CreateDataCatalog for a duplicate name is rejected
    When a GLUE data catalog named "glue_catalog" is created
    And CreateDataCatalog targets the same name "glue_catalog"
    Then CreateDataCatalog answers InvalidRequestException

  Scenario: GetDataCatalog for a missing catalog is rejected
    When GetDataCatalog targets a non-existent catalog
    Then GetDataCatalog answers InvalidRequestException

  Scenario: ListDataCatalogs with pagination
    When 5 data catalogs are created
    And ListDataCatalogs requests MaxResults 3
    Then the response contains 3 catalog summaries
    And a NextToken is returned
    When ListDataCatalogs requests MaxResults 3 with the NextToken
    Then the response contains 3 catalog summaries
    And no NextToken is returned

  Scenario: UpdateDataCatalog replaces the description
    When a GLUE data catalog named "cw_logs_catalog" is created
    And UpdateDataCatalog sets the description to "New CloudWatch Logs Catalog"
    Then GetDataCatalog returns the updated description

  Scenario: DeleteDataCatalog removes the catalog
    When a GLUE data catalog named "UnusedDataCatalog" is created
    And DeleteDataCatalog targets "UnusedDataCatalog"
    Then GetDataCatalog for the deleted catalog answers InvalidRequestException