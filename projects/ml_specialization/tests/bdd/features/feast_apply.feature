Feature: Feast apply on the feature repo
  `feast -c feature_repo apply` registers the checked-in entity and
  feature view definitions against the local registry and online store.
  Nothing executes that seam today — the scenario pins that the repo
  actually applies, not merely that its modules import.

  Scenario: Applying the feature repo registers its definitions
    Given a copy of the feature repo with its offline source parquet
    When I run feast apply on the copied repo
    Then the apply succeeds
    And the registry lists the "hourly_pickup_demand" feature view
    And the registry lists the "pickup_location_id" entity
