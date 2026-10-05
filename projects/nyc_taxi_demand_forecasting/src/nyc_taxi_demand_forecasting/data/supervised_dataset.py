from pathlib import Path

import pandas as pd


class NextHourDemandDatasetBuilder:
    """Build zone-hour demand rows with the next hour as target.

    Example:
        NextHourDemandDatasetBuilder().build(interim_path, processed_path)
    """

    def build(self, trips_path: Path, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        trips = pd.read_parquet(trips_path)
        dataset = self.build_from_trips(trips)
        dataset.to_parquet(output_path, index=False)
        return output_path

    def build_from_trips(self, trips: pd.DataFrame) -> pd.DataFrame:
        hourly_demand = self._hourly_pickups(trips)
        # Join on the actual next hour: a next-observed-row shift mislabels
        # across gaps, and an absent (location, hour+1) row is ambiguous
        # (idle hour vs uncollected data), so only observed labels survive.
        next_hour = hourly_demand.loc[
            :, ["pickup_location_id", "pickup_hour", "pickup_count"]
        ].copy()
        next_hour["pickup_hour"] -= pd.Timedelta(hours=1)
        labeled = hourly_demand.merge(
            next_hour.rename(
                columns={"pickup_count": "next_hour_pickup_count"}
            ),
            on=["pickup_location_id", "pickup_hour"],
            how="left",
        )
        complete_rows = labeled.dropna(
            subset=["next_hour_pickup_count"]
        ).copy()
        complete_rows["next_hour_pickup_count"] = complete_rows[
            "next_hour_pickup_count"
        ].astype(int)
        return complete_rows.reset_index(drop=True)

    def _hourly_pickups(self, trips: pd.DataFrame) -> pd.DataFrame:
        pickup_hour = pd.to_datetime(trips["tpep_pickup_datetime"]).dt.floor(
            "h"
        )
        grouped = trips.assign(pickup_hour=pickup_hour).groupby(
            ["PULocationID", "pickup_hour"], as_index=False
        )
        demand = grouped.size().rename(
            columns={
                "PULocationID": "pickup_location_id",
                "size": "pickup_count",
            }
        )
        return self._add_calendar_columns(
            demand.sort_values(["pickup_location_id", "pickup_hour"])
        )

    def _add_calendar_columns(self, demand: pd.DataFrame) -> pd.DataFrame:
        demand["hour"] = demand["pickup_hour"].dt.hour
        demand["day_of_week"] = demand["pickup_hour"].dt.dayofweek
        demand["is_weekend"] = demand["day_of_week"].isin([5, 6])
        demand["month"] = demand["pickup_hour"].dt.month
        return demand
