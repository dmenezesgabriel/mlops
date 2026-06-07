# Data Preprocessing & Feature Engineering

Raw trip records are transaction logs (individual events). To construct a time-series forecasting model, we must clean, aggregate, and enrich these events into a structured, tabular dataset representing hourly demand.

---

## 1. The Preprocessing Transformation Pipeline

Our preprocessing step cleans raw parquet logs and aggregates them:

1.  **Filtering & Cleaning**:
    *   Trip durations must be strictly positive (dropoff time > pickup time).
    *   Pickup locations must correspond to valid TLC zone IDs ($1 \le \text{PULocationID} \le 263$).
    *   Trip distances must be non-negative.
2.  **Hourly Time-Series Grouping**:
    *   Trips are grouped by `PULocationID` (zone ID) and floored `pickup_hour` (e.g., `2023-01-01 14:00:00`). This produces a regular time series of pickup counts for each zone.
3.  **Supervised Target Creation**:
    *   For each zone, the pickup counts are sorted chronologically. The target column `next_hour_pickup_count` is created by shifting the hourly pickup counts back by 1 hour:
        $$\text{Target}(z, t) = \text{PickupCount}(z, t+1)$$

---

## 2. Advanced Feature Engineering & Encodings

To help linear and tree-based models capture temporal patterns, we use two advanced feature engineering techniques:

### Historical Lags
For time-series forecasting, the best predictor of tomorrow's demand is yesterday's demand, and the best predictor of next hour's demand is last hour's demand. We leverage **historical lags** of the target count:
*   `pickup_count_lag_1`: Demand in the previous hour (captures short-term momentum).
*   `pickup_count_lag_2`: Demand two hours ago (captures short-term trends).
*   `pickup_count_lag_24`: Demand 24 hours ago (captures diurnal seasonality).
*   `pickup_count_lag_168`: Demand 168 hours ago (captures weekly seasonality—same hour of the same day last week).

### Cyclical Temporal Encoding
Standard temporal features (like `hour` from $0$ to $23$) are linear inputs. A linear model struggles to understand that hour 23 and hour 0 are consecutive. To preserve this periodic proximity, we transform the features using **sine and cosine encodings**:

$$\text{hour\_sin} = \sin\left(\frac{2\pi \cdot \text{hour}}{24}\right)$$
$$\text{hour\_cos} = \cos\left(\frac{2\pi \cdot \text{hour}}{24}\right)$$
$$\text{day\_of\_week\_sin} = \sin\left(\frac{2\pi \cdot \text{day\_of\_week}}{7}\right)$$
$$\text{day\_of\_week\_cos} = \cos\left(\frac{2\pi \cdot \text{day\_of\_week}}{7}\right)$$

This maps hour/day variables onto a unit circle, ensuring that periodic boundaries are represented smoothly.

---

## 3. Point-in-Time Joins & Leakage Prevention

In production time-series systems, **data leakage** is a common failure mode. Leakage occurs when features from the future (e.g., lag demand calculated using information after the target hour) are accidentally included in the training frame.

To prevent this, our feature store (**Feast**) performs **Point-in-Time (As-Of) Joins**:
*   For each record in our entity dataframe (representing a specific zone $z$ and event timestamp $t$), Feast joins features (such as historical pickup lags) using only the values that were available *at or before* timestamp $t$.
*   This guarantees that our training dataset matches the exact information state that would exist in production during real-time inference.

---

## 4. Code Reference

Below is the code constructing the supervised training datasets:
{{ include_source("src/nyc_taxi_demand_forecasting/data/supervised_dataset.py") }}
