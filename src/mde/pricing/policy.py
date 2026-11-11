"""A price policy: one multiplier per time band, chosen from an elasticity switchback.

For each band the level with the highest contribution per hour is chosen among the levels that keep at least
`min_ride_share` of the rides seen at the base level (a city agreement and the brand set that floor).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from mde import config
from mde.pricing.experiments import fixed_effects


def band_of(day: date, hour: int) -> str:
    if day.weekday() >= 5:
        return "weekend"
    return "weekday_peak" if (7 <= hour <= 9 or 17 <= hour <= 19) else "weekday_offpeak"


def choose_levels(hours: pd.DataFrame, levels: list[float]) -> tuple[dict, dict]:
    """hours: one row per kept hour with band, level index, contribution c and rides n."""
    floor = config.decide()["pricing"]["min_ride_share"]
    base_idx = levels.index(1.0)
    chosen, table = {}, {}
    for band in sorted(hours["band"].unique()):
        h = hours[hours["band"] == band].copy()
        # effects relative to the base level, with day and hour-of-day fixed effects
        h["lv"] = (h["level"] - base_idx) % len(levels)   # base level first, so it is the reference
        eff_c, eff_n = fixed_effects(h, "c", "lv"), fixed_effects(h, "n", "lv")
        base_c, base_n = float(h.loc[h["lv"] == 0, "c"].mean()), float(h.loc[h["lv"] == 0, "n"].mean())
        rows = {}
        for lv in range(len(levels)):
            i = (lv + base_idx) % len(levels)
            rows[i] = (base_c + eff_c.get(lv, 0.0), base_n + eff_n.get(lv, 0.0))
        ok = {i: r for i, r in rows.items() if r[1] >= floor * base_n}
        best = max(ok, key=lambda i: ok[i][0])
        chosen[band] = levels[best]
        table[band] = {str(levels[i]): {"contribution_per_hour": r[0], "rides_per_hour": r[1]} for i, r in sorted(rows.items())}
    return chosen, table


@dataclass
class BandPolicy:
    multipliers: dict

    def price(self, days: list[date]):
        def f(zone: int, day: int, hour: int, arm: int) -> float:
            return self.multipliers.get(band_of(days[day], hour), 1.0)

        return f
