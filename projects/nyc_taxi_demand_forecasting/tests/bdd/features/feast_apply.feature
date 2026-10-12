Feature: Feast apply and materialize on the feature repo
  `feast -c feature_repo apply` and `LocalFeastMaterializer().apply`
  register the checked-in entity and feature view definitions against the
  local registry, and `FeatureStore.materialize` then loads the offline
  parquet into the online store. These seams ran only against a fake
  FeatureStore until now — the scenarios run real feast end-to-end.

  Scenario: Applying the feature repo registers its definitions
    Given a copy of the feature repo with its offline source parquet
    When I run feast apply on the copied repo
    Then the apply succeeds
    And the registry lists the "hourly_pickup_demand" feature view
    And the registry lists the "pickup_location_id" entity

  Scenario: The materializer apply feeds the online store
    Given a copy of the feature repo with its offline source parquet
    When the materializer applies and materializes the copied repo
    Then the online store serves "3" pickups for location "1"

  Scenario: A second apply never reuses the first repo's modules
    Given a copy of the feature repo with its offline source parquet
    And a second copied repo whose view is named "hourly_pickup_demand_b"
    When the materializer applies both copied repos
    Then the second registry lists only "hourly_pickup_demand_b"
    And the first registry lists "hourly_pickup_demand"
