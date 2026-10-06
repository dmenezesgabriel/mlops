Feature: Taxi Demand Prediction API
  As a consumer of the taxi demand forecasting system
  I want to predict demand for a pickup location
  So that I can optimize dispatching

  Scenario: Successful demand prediction
    Given the champion model is promoted and loaded
    And online features exist for pickup location 142
    When a request is sent to predict demand for pickup location 142
    Then the response status code should be 200
    And the predicted demand should be 12.5

  Scenario: Missing champion model returns service unavailable
    Given the champion model is not loaded
    When a request is sent to predict demand for pickup location 142
    Then the response status code should be 503

  Scenario: Missing online features returns not found
    Given the champion model is promoted and loaded
    But the feature store has no online features
    When a request is sent to predict demand for pickup location 142
    Then the response status code should be 404

  Scenario: Feature store failure returns a generic server error
    Given the champion model is promoted and loaded
    But the feature store fails to answer
    When a request is sent to predict demand for pickup location 142
    Then the response status code should be 500
    And the response detail should not expose internals
