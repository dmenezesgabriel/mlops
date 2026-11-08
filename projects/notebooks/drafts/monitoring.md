# Machine Learning Monitoring

## Model inputs:

- Data Drift
- Data Quality
- Schema

## Model Outputs

- Concept Drift
- Volume
- System metrics

## Model Performance

- Accuracy/Reacall
- Bias/Fairness
- Explainability
- Business KPIs

## Data Quality Examples

**External Changes**:

- An input sensor is damaged causing bad data
- Data was manually entered incorrectly
- A camera is pointing in the wrong direction

**Schema changes**:

- A software library outputs a different format than before

**Pipeline bugs**:

- Anywhere

## Data Drift Examples

Input data for predictions are no longer as close to the original training data.

- Seasonality Changes
- New group of users
- Consumer preferences have changed

## Concept Drift

The incoming data didn't change, but the output no longer mathces.

- Housing market (prices then years ago were much smaller
- Covid-19 (complete word changes)

## Detecting Bias in Production with Segmentation

Segments can be on features included in training or in groups not explicity used for training

Ex: higer credit card limits for men

## Model Explainability

- Shap

## Metrics

- Hellinger Distance (Recommended)
- Jensen Shannon (JS) Divergence
- Kullback-Leber (KL) Divergence
- Population Stability Index (PSI)

## Software system metrics

- Latency
- Error rate
- memory use

## Data quality metrics

- missing values
- type mismatch
- range violations

## ML model quality metrics

### Classification

- **Accuracy**: overall share of the correct predictions
- **Precision**: correctness when predicting the target classe
- **Recall**: ability to find all objects of the target class.
- **F1-score**: harmonic mean of precision and recall.
- **ROC AUC**: ability to discriminate between classes across all classification thresholds
- **Log-loss**: how close the predicted probability is to the actual value

### Regression

- **Mean Error (ME)**: an average of all errors. Positives and negatives cancel each other.
- **Mean Absolute Error (MAE)**: an average of all absolute errors.
- **Root Mean Square Error (RMSE)**: standard deviation of the residuals. Penalizes larger errors.
- **Mean Absolute Percentage Error (MAPE)**: an average of all absolte errors in %.
- **Symmetric MAPE (SMAPE)**: different penalty for over or underestimation.

### Ranking

_Relative order of the objects (Ex: Recomendations)_

- Cumulative gain
- Discounted cumulative gain (DCG)
- Normalized DCG (NDCG)
- Precision @k
- Recall @k
- Lift @k
- top-k accuracy
- MAP

## Business KPIs

- clicks
- purchases
- loan approval rate
- cost savings

## Data quality

Any issues with quality and integrity

## Data Drift

Changes in the input feature distributions

## Output drift

Change in the models predictions

