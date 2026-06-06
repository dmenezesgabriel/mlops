# Problem Framing

In machine learning engineering, framing the problem properly is the foundation of any successful system. For the NYC Taxi Demand Forecasting project, our goal is to solve a classic operational efficiency problem for urban mobility.

## The Business Objective
Maximize driver utilization and minimize passenger wait times by predicting exactly where demand will occur next. Having reliable taxi demand forecasts allows fleet dispatchers to position taxis in high-demand zones *before* passengers request rides.

## The ML Task
We frame this as a **supervised regression task**:
- **Target**: Predict the number of yellow taxi pickups in a given NYC TLC zone during the next hour.
- **Features**: Historical hourly pickup counts, calendar features (hour, day of week, is_weekend, month).

## Target Definition
Given a taxi zone ID $z$ and an hour window $t$, our target column is:
$$\text{Target}(z, t) = \text{PickupCount}(z, t+1)$$

By shifting our pickup counts backwards by one hour for each zone, we create the target `next_hour_pickup_count` from historical event logs.

## Educational Goal
This project is built to demonstrate a reproducible MLOps pipeline. The first local workflow is optimized for fast developer iteration, running entirely on a local machine using local file-based databases (**DuckDB** and **SQLite**), before orchestrating to production-grade server resources.
