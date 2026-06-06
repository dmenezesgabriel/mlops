# Model Training & Algorithm Selection

Once historical features are retrieved from Feast using point-in-time joins, we proceed to model training. Designing a production-ready model requires selecting an algorithm that matches the statistical properties of the dataset and the runtime requirements of the serving environment.

---

## 1. Comparative Algorithm Selection Trade-offs

During architectural design, we evaluated three distinct forecasting algorithms:

| Algorithm | Pros | Cons | Decision |
| :--- | :--- | :--- | :--- |
| **Ridge Regression (L2 Linear)** | Highly stable; closed-form solution (guaranteed global optimum); low latency; robust to multicollinear features (highly correlated consecutive lags). | Cannot capture complex non-linear feature interactions (e.g. zone-specific hour patterns) without manual interaction feature engineering. | **Selected (Baseline & Production)** |
| **Lasso Regression (L1 Linear)** | Performs feature selection by driving coefficients of non-predictive variables to exactly zero. | In the presence of highly correlated lags (e.g. lag 1 and lag 2), Lasso randomly selects one and ignores the others, leading to model instability. | Rejected |
| **Gradient Boosted Trees (LightGBM/XGBoost)** | State-of-the-art accuracy; handles zero-inflation, non-linear relationships, and complex interaction features automatically. | Prone to overfitting on sparse zones; cannot extrapolate trends outside the range of historical training values; higher serving latency and memory footprint. | Future Champion candidate |

---

## 2. Mathematical Formalization of L2 Regularization (Ridge)

To prevent overfitting on temporal patterns and handle high correlation between consecutive hourly lags (multicollinearity), we employ **Ridge Regression**.

The model fits coefficients $\beta$ by minimizing the sum of squared errors plus a penalty term on the squared $L_2$ norm of the coefficients:

$$\min_{\beta} \left( \|y - X\beta\|_2^2 + \alpha \|\beta\|_2^2 \right)$$

Solving this optimization problem analytically yields the closed-form equation:

$$\beta = (X^T X + \alpha I)^{-1} X^T y$$

*   $X$: The design matrix (independent features + a column of ones for intercept).
*   $y$: The target vector (`next_hour_pickup_count`).
*   $\alpha$: The regularization hyperparameter ($\alpha > 0$). Larger values of $\alpha$ shrink coefficients closer to zero, reducing variance and preventing the model from fitting to high-frequency noise.
*   $I$: The identity matrix, modified in our code so that the regularization penalty is not applied to the intercept term.

---

## 3. Production Model Tracking & Artifact Registry

To maintain auditability under the CD4ML framework, every training run registers its parameters, metrics, and code environment to a centralized registry using **MLflow**:

1.  **Tracking Store**: Metrics (MAE, RMSE, $R^2$) and parameters ($\alpha$, dataset version) are logged to a relational tracking database (backed by SQLite).
2.  **Artifact Store**: The trained weights $\beta$ are packaged as a custom MLflow `pyfunc` model (`PyfuncDemandModel`) and stored as a serialized python pickle.
3.  **Model Registry**: High-performing models are registered in the registry as `nyc_taxi_demand_forecaster` with version control. This decoupling allows serving APIs to fetch models by stage (e.g., `Staging` or `Production`) without rebuilding API containers.

---

## 4. Code Reference

Below is the core training and registry implementation:
{{ include_source("src/nyc_taxi_demand_forecasting/models/training.py") }}
