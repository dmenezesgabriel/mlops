Feature: Canonical Athena service model

  The frozen reference model vendored under research_repos/aws-cli is the
  single source of truth for the wire protocol. The botocore installed by the
  lockfile must keep shipping a byte-identical model and resolving dispatch
  the same way, or protocol parity silently breaks.

  Background:
    Given the canonical Athena service-2.json

  Scenario: Installed botocore model is byte-identical to the reference
    Given a decompressed copy of the installed botocore Athena model
    When the installed model is compared byte-for-byte with the reference
    Then the two models are identical

  Scenario: The canonical model declares the JSON-1.1 wire protocol
    Then the model declares 70 operations
    And the model uses the json protocol with jsonVersion 1.1
    And the metadata targets the athena endpoint prefix

  Scenario: Every operation dispatches as the final segment of X-Amz-Target
    Then every operation's X-Amz-Target ends with the operation name after the final dot