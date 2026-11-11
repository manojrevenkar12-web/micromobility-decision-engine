"""A simulated city: zones, the true demand (intents) per zone-hour, weather and trip geography.

This module is the hidden truth. Decision code never imports it (tests/test_isolation.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from functools import cached_property

import numpy as np

from mde import config

TYPES = ["center", "mixed", "residential", "campus", "station", "park"]


@dataclass
class City:
    name: str
    grid: int
    zone_type: np.ndarray       # (Z,) index into TYPES
    xy: np.ndarray              # (Z, 2) cell coordinates
    days: list[date]
    rain_hours: np.ndarray      # (D, 24) bool
    temp_c: np.ndarray          # (D,)
    intents: np.ndarray         # (D, 24, Z) true expected intents per zone-hour
    commuter_share: np.ndarray  # (D, 24)
    fleet: int
    seed: int

    @property
    def Z(self) -> int:
        return self.grid * self.grid

    @cached_property
    def km(self) -> np.ndarray:
        d = self.xy[:, None, :] - self.xy[None, :, :]
        return np.sqrt((d**2).sum(-1)) * 0.5 + 0.25  # 500 m cells; trips inside a cell ~250 m

    @cached_property
    def neighbours(self) -> list[np.ndarray]:
        out = []
        for z in range(self.Z):
            x, y = self.xy[z]
            nb = [i for i in range(self.Z) if i != z and abs(self.xy[i, 0] - x) <= 1 and abs(self.xy[i, 1] - y) <= 1]
            out.append(np.array(nb))
        return out

    def attraction(self, hour: int, weekday: bool) -> np.ndarray:
        """Where trips end: the center and stations in the morning, homes in the evening."""
        t = self.zone_type
        a = np.ones(self.Z)
        work = np.isin(t, [TYPES.index("center"), TYPES.index("station"), TYPES.index("campus")])
        home = t == TYPES.index("residential")
        if weekday and 6 <= hour <= 10:
            a[work] *= 3.0
        elif weekday and 16 <= hour <= 20:
            a[home] *= 2.5
        if not weekday and 11 <= hour <= 19:
            a[t == TYPES.index("park")] *= 3.0
            a[t == TYPES.index("center")] *= 1.5
        return a


def _hour_profile(weekday: bool) -> np.ndarray:
    h = np.arange(24)
    if weekday:
        p = 0.08 + 0.9 * np.exp(-((h - 8.2) ** 2) / 2.2) + 0.85 * np.exp(-((h - 18) ** 2) / 3.5) \
            + 0.45 * np.exp(-((h - 13) ** 2) / 6) + 0.25 * np.exp(-((h - 22) ** 2) / 3)
    else:
        p = 0.10 + 0.75 * np.exp(-((h - 15) ** 2) / 12) + 0.35 * np.exp(-((h - 23) ** 2) / 4)
    p[1:6] *= 0.25
    return p


def build(name: str) -> City:
    cfg = config.world()
    c = cfg["cities"][name]
    rng = np.random.default_rng(c["seed"])
    g = c["grid"]
    xy = np.array([(x, y) for y in range(g) for x in range(g)], dtype=float)
    dist_c = np.sqrt(((xy - np.array(c["center"])) ** 2).sum(1))
    zt = np.where(dist_c <= cfg["zones"]["center_radius"], 0, np.where(dist_c <= cfg["zones"]["mixed_radius"], 1, 2))
    for key, t in (("campus", 3), ("stations", 4), ("parks", 5)):
        for x, y in c[key]:
            zt[int(y) * g + int(x)] = t

    s = cfg["season"]
    d0, d1 = date.fromisoformat(s["start"]), date.fromisoformat(s["end"])
    days = [d0 + timedelta(i) for i in range((d1 - d0).days + 1)]
    D, Z = len(days), g * g
    rain_day = rng.random(D) < cfg["time"]["rain_day_prob"]
    rain_hours = np.zeros((D, 24), bool)
    for d in np.where(rain_day)[0]:
        start = rng.integers(6, 18)
        rain_hours[d, start : start + rng.integers(3, 9)] = True
    month_temp = {4: 13, 5: 18, 6: 22, 7: 25, 8: 24, 9: 19, 10: 13}
    temp = np.array([month_temp[d.month] for d in days]) + rng.normal(0, 3.5, D)

    base = np.array([cfg["zones"]["base_rate"][t] for t in TYPES])[zt] * c["demand_scale"]
    base = base * rng.lognormal(0, 0.25, Z)  # zones of the same type still differ
    intents = np.zeros((D, 24, Z))
    commuter = np.zeros((D, 24))
    sf = cfg["time"]["season_factor"]
    for i, d in enumerate(days):
        wk = d.weekday() < 5
        prof = _hour_profile(wk)
        f = sf[str(d.month)] * (1.0 if temp[i] < cfg["time"]["hot_threshold_c"] else 0.9)
        level = base[None, :] * prof[:, None] * f
        if not wk:
            level[:, zt == 5] *= 2.0
            level[:, zt == 0] *= 1.2
        level[rain_hours[i]] *= cfg["time"]["rain_factor"]
        intents[i] = level
        h = np.arange(24)
        peak = ((h >= 7) & (h <= 9)) | ((h >= 17) & (h <= 19))
        commuter[i] = np.where(wk & peak, 0.7, 0.15)
    ev = cfg["events"]["competitor"]
    if ev["city"] == name:
        start = days.index(date.fromisoformat(ev["start"]))
        east = xy[:, 0] >= ev["x_from"]
        intents[start:, :, east] *= 1 + ev["effect"]
    return City(name, g, zt, xy, days, rain_hours, temp, intents, commuter, c["fleet"], c["seed"])
