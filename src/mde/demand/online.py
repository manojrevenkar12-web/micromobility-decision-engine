"""The forecast as the planner calls it at a shift: demand per zone over the next hours."""

from __future__ import annotations

import numpy as np
import pandas as pd

from mde import config
from mde.demand.censoring import zone_hour_table
from mde.demand.forecast import Forecaster, recent_levels
from mde.world.sim import Observation


def forecast_fn(model: Forecaster):
    def fn(obs: Observation, window) -> np.ndarray:
        """(hours, Z) rides demanded per zone in each hour of the planning horizon."""
        H = config.decide()["planner"]["horizon_hours"]
        Z = obs.grid * obs.grid
        opens, rides = window.opens(), window.rides()
        first = int(min(opens["day"].min(), rides["day"].min()))
        n_days = obs.day_index - first
        table = zone_hour_table(opens[opens["day"] < obs.day_index], rides[rides["day"] < obs.day_index], n_days, Z, first)
        recent = recent_levels(table, model.target, obs.day_index)
        hours = [h for h in range(obs.hour + 1, obs.hour + 1 + H) if h < 24]
        rows = pd.DataFrame([(obs.day_index, h, z) for h in hours for z in range(Z)], columns=["day", "hour", "zone"])
        weather = pd.DataFrame({"day": obs.day_index, "hour": range(24), "rain": obs.rain_hours_today, "temp": obs.temp_today})
        pred = model.predict(rows, recent, weather)
        return pred.reshape(len(hours), Z)

    return fn
