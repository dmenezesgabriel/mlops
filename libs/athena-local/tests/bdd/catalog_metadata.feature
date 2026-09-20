Feature: Catalog metadata reads through Glue

  The four catalog-introspection operations — ListDatabases, GetDatabase,
  ListTableMetadata, GetTableMetadata — are served from the live moto Glue
  store (ADR-0005), keeping API answers consistent with what the Trino engine
  sees. Only GLUE-type data catalogs serve database and table metadata; unknown
  catalogs answer InvalidRequestException, and missing Glue entities answer
  MetadataException (HTTP 400, the AWS-documented custom-metastore error).

  Background:
    Given a fresh catalog registry with the Glue store

  Scenario: ListDatabases returns the databases in a GLUE catalog
    Given the glue store contains databases default and analytics
    When ListDatabases targets the AwsDataCatalog catalog
    Then the response lists the databases default and analytics

  Scenario: GetDatabase returns the database details
    Given the glue store contains database "sampledb" with description "Sample database" and parameters CreatedBy=Athena, EXTERNAL=TRUE
    When GetDatabase targets "sampledb" in the AwsDataCatalog catalog
    Then the response is the database "sampledb" with description and parameters

  Scenario: GetDatabase for a missing database answers MetadataException
    When GetDatabase targets a non-existent database
    Then GetDatabase answers MetadataException

  Scenario: ListDatabases for an unknown catalog answers InvalidRequestException
    When ListDatabases targets a non-existent catalog
    Then ListDatabases answers InvalidRequestException

  Scenario: ListTableMetadata filters by expression and paginates
    Given the glue store contains tables countries, cities and orders in database "geo"
    When ListTableMetadata targets database "geo" with expression "c.*" and MaxResults 1
    Then the response lists 1 table matching expression "c.*"
    And a NextToken is returned
    When ListTableMetadata requests the next page for database "geo" with expression "c.*"
    Then the response lists 1 table matching expression "c.*"
    And no NextToken is returned

  Scenario: GetTableMetadata returns the full wire shape
    Given the glue store contains table "counties" in database "sampledb" with columns, partition keys, and parameters
    When GetTableMetadata targets table "counties" in database "sampledb"
    Then the response has name, table type, columns, partition keys, parameters, and a CreateTime
    And the table metadata lists columns name and population

  Scenario: GetTableMetadata for a missing table answers MetadataException
    When GetTableMetadata targets a non-existent table
    Then GetTableMetadata answers MetadataException