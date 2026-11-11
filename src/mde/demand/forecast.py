"""Zone-hour demand forecast: one global LightGBM model over all zones.

Features are what is known at planning time: the zone and its position, the calendar, the weather forecast,
and the zone's recent demand level (last 14 days, same hour band), which carries the season forward.
The target is either the naive (censored) or the corrected demand from mde.demand.censoring.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import lightgbm as lgb
import numpy as np
import pandas as pd

from mde import config
from mde.demand.censoring import hour_band

FEATURES = ["zone", "x", "y", "hour", "weekday", "weekend", "rain", "temp", "recent", "recent_all"]


def add_recent(table: pd.DataFrame, target: str, lookback: int = 14) -> pd.DataFrame:
    """Mean of the target over the previous `lookback` days for the zone and hour band (no same-day data)."""
    t = table.copy()
    t["band"] = hour_band(t["hour"])
    daily = t.groupby(["zone", "band", "day"])[target].mean().unstack("day")
    rolled = daily.T.rolling(lookback, min_periods=3).mean().shift(1).T
    rec = rolled.stack().rename("recent").reset_index()
    t = t.merge(rec, on=["zone", "band", "day"], how="left")
    daily_all = t.groupby(["zone", "day"])[target].mean().unstack("day")
    rolled_all = daily_all.T.rolling(lookback, min_periods=3).mean().shift(1).T
    t = t.merge(rolled_all.stack().rename("recent_all").reset_index(), on=["zone", "day"], how="left")
    return t


@dataclass
class Forecaster:
    target: str
    xy: np.ndarray
    day0: object                      # date of day index 0
    model: lgb.LGBMRegressor | None = None
    history: pd.DataFrame = field(default_factory=pd.DataFrame)

    def frame(self, t: pd.DataFrame, weather: pd.DataFrame) -> pd.DataFrame:
        from datetime import timedelta

        t = t.merge(weather, on=["day", "hour"], how="left")
        t["x"] = self.xy[t["zone"], 0]
        t["y"] = self.xy[t["zone"], 1]
        wd = np.array([(self.day0 + timedelta(int(d))).weekday() for d in range(int(t["day"].max()) + 1)])
        t["weekday"] = wd[t["day"]]
        t["weekend"] = (t["weekday"] >= 5).astype(int)
        t["rain"] = t["rain"].astype(float)
        return t

    def fit(self, table: pd.DataFrame, weather: pd.DataFrame) -> Forecaster:
        c = config.decide()["forecast"]
        t = self.frame(add_recent(table, self.target), weather).dropna(subset=["recent"])
        self.model = lgb.LGBMRegressor(objective="poisson", num_leaves=c["num_leaves"], learning_rate=c["learning_rate"],
                                       n_estimators=c["n_estimators"], min_child_samples=c["min_child_samples"],
                                       verbose=-1, n_jobs=2)
        self.model.fit(t[FEATURES], t[self.target], categorical_feature=["zone"])
        return self

    def predict(self, rows: pd.DataFrame, recent: pd.DataFrame, weather: pd.DataFrame) -> np.ndarray:
        """rows: day, hour, zone. recent: zone, band, recent, recent_all for the planning day."""
        r = rows.copy()
        r["band"] = hour_band(r["hour"])
        r = r.merge(recent, on=["zone", "band"], how="left")
        r = self.frame(r, weather)
        return self.model.predict(r[FEATURES])


def recent_levels(table: pd.DataFrame, target: str, day: int, lookback: int = 14) -> pd.DataFrame:
    """The zone's mean target over the `lookback` days before `day`, by hour band and overall."""
    t = table[(table["day"] < day) & (table["day"] >= day - lookback)].copy()
    t["band"] = hour_band(t["hour"])
    by_band = t.groupby(["zone", "band"])[target].mean().rename("recent").reset_index()
    overall = t.groupby("zone")[target].mean().rename("recent_all").reset_index()
    return by_band.merge(overall, on="zone")
