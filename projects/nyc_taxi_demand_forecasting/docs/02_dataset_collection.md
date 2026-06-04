# Dataset Collection

The collector stores immutable monthly TLC parquet files under `data/raw` and skips files already present locally.

```bash
make collect PROJECT=nyc_taxi_demand_forecasting
```
