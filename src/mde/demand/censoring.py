"""Observed rides are censored demand: when no scooter is near, the ride never happens and never shows up
in the ride table. App opens show some of it. This module turns logs into a demand target.

    naive target      rides that started in the zone-hour
    corrected target  every app open in the zone-hour times the conversion seen when a scooter was near
                      (same zone type proxy: zone and hour band), so opens that found nothing count too
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from mde import config


def hour_band(h: pd.Series | np.ndarray) -> np.ndarray:
    h = np.asarray(h)
    return np.select([h < 6, h < 10, h < 16, h < 20], [0, 1, 2, 3], 4)


def zone_hour_table(opens: pd.DataFrame, rides: pd.DataFrame, n_days: int, Z: int, d_from: int = 0) -> pd.DataFrame:
    """One row per (day, hour, zone) with rides, opens, opens with a scooter nearby, and the targets."""
    idx = pd.MultiIndex.from_product([range(d_from, d_from + n_days), range(24), range(Z)], names=["day", "hour", "zone"])
    t = pd.DataFrame(index=idx)
    t["rides"] = rides.groupby(["day", "hour", "start"]).size().rename_axis(["day", "hour", "zone"])
    o = opens.groupby(["day", "hour", "zone"])
    t["opens"] = o.size()
    t["opens_nearby"] = o["nearby"].sum()
    t["rented_nearby"] = opens[opens["nearby"]].groupby(["day", "hour", "zone"])["rented"].sum()
    t = t.fillna(0.0).reset_index()
    t["band"] = hour_band(t["hour"])
    min_n = config.decide()["forecast"]["min_nearby_opens"]
    g = t.groupby(["zone", "band"])[["opens_nearby", "rented_nearby"]].sum()
    overall = t.groupby("band")[["opens_nearby", "rented_nearby"]].sum()
    conv_band = (overall["rented_nearby"] / overall["opens_nearby"].clip(lower=1)).rename("conv_band")
    g = g.join(conv_band, on="band")
    shrink = g["opens_nearby"] / (g["opens_nearby"] + min_n)
    g["conversion"] = shrink * g["rented_nearby"] / g["opens_nearby"].clip(lower=1) + (1 - shrink) * g["conv_band"]
    t = t.join(g["conversion"], on=["zone", "band"])
    t["demand_naive"] = t["rides"]
    t["demand_corrected"] = t["opens"] * t["conversion"]
    return t
