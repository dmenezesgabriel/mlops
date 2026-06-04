.PHONY: collect preprocess features train tune evaluate deploy monitor

collect preprocess features train tune evaluate deploy monitor:
	uv run python -m nyc_taxi_demand_forecasting.interfaces.cli $@ --config configs/project.yaml
