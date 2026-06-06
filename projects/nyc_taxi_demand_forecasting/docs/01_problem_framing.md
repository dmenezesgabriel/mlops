# Problem Framing & Business Trade-offs

In production machine learning engineering, framing a prediction task requires aligning statistical models with core business objectives. For the NYC Taxi Demand Forecasting system, we address a classic resource-allocation and spatial-routing optimization challenge in urban mobility.

## 1. The Business Objective & Operational Impact

The high-level goal is to **maximize driver utilization (reduce passenger-search time)** and **minimize passenger wait times (dispatch latency)**. By predicting ride demand across NYC Taxi and Limousine Commission (TLC) zones, fleet dispatchers can proactively recommend driver positioning *before* the ride requests occur.

### Cost-Benefit Trade-offs in Forecast Errors

In a real-world dispatch system, forecasting errors are not symmetric in their operational impact:

*   **Overestimating Demand (False Positives / High Forecast)**:
    *   *Operational Consequence*: Drivers are routed to zones where demand does not materialize, causing them to sit idle.
    *   *Business Penalty*: Increases driver frustration, wastes fuel/electricity, increases empty vehicle miles traveled (eVMT), and reduces hourly driver earnings, which directly triggers driver churn from the platform.
*   **Underestimating Demand (False Negatives / Low Forecast)**:
    *   *Operational Consequence*: Insufficient vehicles are positioned in active zones, leaving passenger requests unserved.
    *   *Business Penalty*: Passengers experience high wait times, leading to ride cancellations and customer churn to competing platforms. It also causes localized "surge pricing" spikes that may negatively affect brand perception.

### Temporal Horizon Selection

We predict demand at a **1-hour temporal resolution**. 
*   *Why not 5 minutes?* A 5-minute window is too short for vehicles to physically reposition between distant NYC zones, leading to high routing friction and feedback loops.
*   *Why not 1 day?* A daily forecast fails to capture rapid morning/evening rush hour transitions and real-time weather changes. 
*   *Conclusion*: A 1-hour horizon matches the physical routing latency of passenger cars across boroughs while remaining highly responsive to temporal demand shifts.

---

## 2. Machine Learning Task Formulation

We frame this as a **spatio-temporal supervised regression task**:

*   **Target**: Predict the absolute count of yellow taxi pickups in a specific TLC zone $z$ during the target hour $t+1$.
*   **Features**: Historical hourly pickup counts, calendar features (diurnal cycles, weekly patterns, weekend indicators, and month seasonality).

### Mathematical Target Definition

Given a TLC zone ID $z \in \{1, \dots, 263\}$ and an hour window $t$, the target variable $y_{z, t+1}$ is defined as:

$$y_{z, t+1} = \text{PickupCount}(z, t+1)$$

By shifting historical transaction logs backwards by one hour, we frame this as predicting the immediate future step $t+1$ using features known up to step $t$.

---

## 3. Project Goal & Pipeline Architecture

This project implements a production-grade, end-to-end MLOps pipeline to serve this model with strict validation. The workflow is split into a local developer setup (relying on **DuckDB** for analytics and **SQLite** for metadata store) and standard cloud adapters, showcasing the CD4ML (Continuous Delivery for Machine Learning) lifecycle including feature store serving, experiment tracking, and automated quality gates.
