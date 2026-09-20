Feature: Resource tagging

  TagResource, UntagResource, and ListTagsForResource address workgroup and
  data catalog ARNs (arn:aws:athena:<region>:<account>:<type>/<name>).
  Unknown resources answer ResourceNotFoundException (the model declares it
  for all three ops); malformed ARNs answer InvalidRequestException.

  Background:
    Given a fresh tagging registry

  Scenario: TagResource then ListTagsForResource round-trips the tags
    When TagResource adds "Division: West" and "Team: Big Data" to the primary workgroup
    Then ListTagsForResource returns the two tags
    When UntagResource removes the "Team" key from the primary workgroup
    Then ListTagsForResource returns only the "Division" tag

  Scenario: An untagged resource lists an empty tag set
    Given the primary workgroup has no tags
    When ListTagsForResource targets the primary workgroup
    Then the response contains an empty tag list

  Scenario: Data catalogs accept tags
    Given a LAMBDA data catalog named "dynamo_db_catalog"
    When TagResource adds "Division: Mountain" to the data catalog
    Then ListTagsForResource returns the catalog tag

  Scenario: Tagging an unknown resource is rejected with not found
    When TagResource targets a non-existent workgroup ARN
    Then TagResource answers ResourceNotFoundException

  Scenario: A malformed ARN is rejected as invalid request
    When TagResource targets the malformed ARN "not-an-arn"
    Then TagResource answers InvalidRequestException