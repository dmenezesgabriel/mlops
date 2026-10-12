Feature: Batch demand scoring
  `BatchDemandPredictor.predict` loads the pyfunc model at the requested
  MLflow URI, scores a parquet of processed demand rows projected onto the
  hourly-demand feature columns, and writes the scored frame to the
  requested output path.

  Scenario: Scoring writes predictions to the output parquet
    Given a parquet of processed demand rows
    And the served model returns the predictions 12.5 and 8.0
    When batch predict runs for "models:/model/1"
    Then the output parquet carries the predictions 12.5 and 8.0
    And the model saw only the feature columns
    And the served model was loaded from "models:/model/1"
