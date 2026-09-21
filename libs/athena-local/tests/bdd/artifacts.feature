Feature: Query result artifacts

  Query results are persisted to the workgroup's output location before an
  execution reaches SUCCEEDED (ADR-0009 #4), in the byte shapes awswrangler
  reads (ADR-0010): a header-quoted {QueryID}.csv with a {QueryID}.csv.metadata
  sidecar for DML results, a headerless tab-delimited {QueryID}.txt for
  DDL/UTILITY results, and a {QueryID}-manifest.csv listing every created file
  for CTAS — which also fills Statistics.DataManifestLocation so
  wr.athena.read_sql_query reads the parquet output (awswrangler/athena/_read.py:62-81).

  Background:
    Given a fresh object store and a result location "s3://results-bucket/analytics/"

  Scenario: A SELECT persists a header-quoted CSV and its metadata sidecar
    Given a SUCCEEDED SELECT with columns "id" and "name" and 2 rows
    When the artifact writer persists the execution
    Then the CSV carries the quoted header row first
    And the sidecar records the columns and row count

  Scenario: A CTAS manifests exactly the files it created
    Given a CTAS wrote 2 parquet files under "s3://ctas-bucket/t1/"
    When the artifact writer persists the execution
    Then the manifest lists each parquet file on its own line
    And DataManifestLocation points at the manifest file