# Model Evaluation & Quality Gates

In Continuous Delivery for Machine Learning (CD4ML), we treat code, data, and models as first-class citizens. Just as code is guarded by unit tests, models must be guarded by statistical **Quality Gates** to prevent regressions before deployment.

---

## 1. Deep Dive on Evaluation Metrics

We evaluate our model using three complementary regression metrics:

### Mean Absolute Error (MAE)
MAE measures the average magnitude of prediction errors, without considering their direction:

$$\text{MAE} = \frac{1}{n} \sum_{i=1}^n |y_i - \hat{y}_i|$$

*   *Interpretation*: Expressed in the target's unit (number of taxi pickups). An MAE of 11.5 means that, on average, our forecasts miss the actual hourly pickup count by approximately 11.5 rides.
*   *Robustness*: Highly robust to statistical outliers. It is useful for representing typical error behaviors.

### Root Mean Squared Error (RMSE)
RMSE is the square root of the average of squared prediction errors:

$$\text{RMSE} = \sqrt{\frac{1}{n} \sum_{i=1}^n (y_i - \hat{y}_i)^2}$$

*   *Interpretation*: By squaring the errors before averaging, RMSE penalizes larger errors more heavily.
*   *Business Significance*: Highly critical for fleet logistics. A huge forecasting miss (e.g. predicting 10 pickups when 200 occur) is operationally disastrous because it leaves hundreds of passengers stranded. Dispatchers prefer a model with a slightly higher MAE if it maintains a significantly lower RMSE (fewer catastrophic misses).

### Coefficient of Determination ($R^2$)
$R^2$ represents the proportion of variance in the target variable that is predictable from the independent features:

$$R^2 = 1 - \frac{\sum_{i=1}^n (y_i - \hat{y}_i)^2}{\sum_{i=1}^n (y_i - \bar{y})^2}$$

*   *Interpretation*: Scale-free metric ranging from $-\infty$ to $1$. An $R^2$ of $0.65$ indicates that our model explains 65% of the demand variance compared to a naive historical baseline model ($\bar{y}$).

---

## 2. Automated Quality Gates

To automate deployment safely, our pipeline implements a gating mechanism:

```python
metrics.require_within(config.evaluation)
```

1.  **Retrieve Candidate Metrics**: The pipeline pulls the candidate model version from MLflow and runs predictions on the test set.
2.  **Evaluate Thresholds**: The calculated metrics are compared against maximum error thresholds defined in `configs/project.yaml`:
    *   `max_mae`: Max MAE permitted.
    *   `max_rmse`: Max RMSE permitted.
3.  **Deployment Block**: If the candidate model's MAE or RMSE exceeds the thresholds, the evaluation script raises a validation exception and aborts. This stops downstream deployment stages, keeping the previous production model active.

---

## 3. Pipeline Implementation

Below is the code executing the model evaluation and gating:
{{ include_source("src/nyc_taxi_demand_forecasting/pipelines/evaluate.py") }}
