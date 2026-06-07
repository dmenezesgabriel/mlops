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
