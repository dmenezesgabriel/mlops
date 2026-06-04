# NYC Taxi Demand Forecasting

Local-first demand forecasting for NYC TLC yellow taxi pickups.

## Commands

```bash
make collect PROJECT=nyc_taxi_demand_forecasting
make preprocess PROJECT=nyc_taxi_demand_forecasting
make features PROJECT=nyc_taxi_demand_forecasting
make train PROJECT=nyc_taxi_demand_forecasting
make evaluate PROJECT=nyc_taxi_demand_forecasting
```

The project uses local parquet files, Feast with DuckDB, and MLflow with SQLite.
