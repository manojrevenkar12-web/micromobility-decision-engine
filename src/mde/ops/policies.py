"""Operations policies: which batteries to swap and which scooters to move at each shift.

heuristic   the status quo: swap the emptiest batteries; move scooters towards last fortnight's ride starts
planner     forecast demand for each of the next hours and the scooters that will arrive with rides, find how
            many scooters each zone needs on hand to never run out (the peak of cumulative demand minus
            arrivals), and spend swaps and moves where an extra rentable scooter is worth most:
            value of the k-th scooter in a zone = margin x P(need >= k), need ~ Normal(peak, sd)

The planner is the same code whatever forecast it is given (censored, corrected, or in evaluation the truth).
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable

import numpy as np
import pandas as pd
from scipy.stats import norm

from mde import config
from mde.world.sim import Logs, Observation, Plan

# Forecast of rides demanded per zone in each hour of the planning horizon: (obs, window) -> (hours, Z)
ForecastFn = Callable[[Observation, "LogWindow"], np.ndarray]


class LogWindow:
    """The last N days of logs as data frames, updated incrementally (logs are append-only)."""

    def __init__(self, days: int):
        self.days = days
        self.frames: deque[tuple[int, pd.DataFrame, pd.DataFrame]] = deque()
        self._o = self._r = 0
        self._last_day = -1

    def update(self, logs: Logs, today: int) -> None:
        if today == self._last_day:
            return
        o = pd.DataFrame(logs.opens[self._o :], columns=["day", "hour", "zone", "nearby", "multiplier", "arm", "rented"])
        r = pd.DataFrame(logs.rides[self._r :], columns=["day", "hour", "start", "end", "minutes", "revenue",
                                                          "battery_used", "arm", "multiplier"])
        self._o, self._r, self._last_day = len(logs.opens), len(logs.rides), today
        for d in sorted(set(o["day"]) | set(r["day"])):
            self.frames.append((d, o[o["day"] == d], r[r["day"] == d]))
        while self.frames and self.frames[0][0] < today - self.days:
            self.frames.popleft()

    def opens(self) -> pd.DataFrame:
        return pd.concat([f[1] for f in self.frames]) if self.frames else pd.DataFrame()

    def rides(self) -> pd.DataFrame:
        return pd.concat([f[2] for f in self.frames]) if self.frames else pd.DataFrame()


def effective_supply(obs: Observation, Z: int) -> np.ndarray:
    p = config.decide()["planner"]
    w = np.where(obs.vehicle_battery >= p["low_battery_pct"], 1.0,
                 np.where(obs.vehicle_battery >= p["rentable_battery_pct"], p["low_battery_weight"], 0.0))
    return np.bincount(obs.vehicle_zone, weights=w, minlength=Z)


class Heuristic:
    name = "heuristic"

    def __init__(self):
        self.window = LogWindow(config.decide()["heuristic"]["lookback_days"])

    def plan(self, obs: Observation) -> Plan:
        c = config.decide()["heuristic"]
        Z = obs.grid * obs.grid
        b = obs.vehicle_battery
        low = np.where(b < c["swap_below_pct"])[0]
        swap = [int(v) for v in low[np.argsort(b[low])][: obs.swaps]]
        self.window.update(obs.logs, obs.day_index)
        rides = self.window.rides()
        starts = np.bincount(rides["start"], minlength=Z).astype(float) if len(rides) else np.ones(Z)
        good = b >= c["swap_below_pct"]
        swapped = np.zeros(len(b), bool)
        swapped[swap] = True
        usable = good | swapped
        count = np.bincount(obs.vehicle_zone[usable], minlength=Z).astype(float)
        target = starts / starts.sum() * usable.sum()
        gap = count - target
        move = []
        pool = {z: sorted(np.where((obs.vehicle_zone == z) & usable)[0].tolist(), key=lambda v: -b[v]) for z in range(Z)}
        for _ in range(obs.moves):
            src, dst = int(np.argmax(gap)), int(np.argmin(gap))
            if gap[src] < 1 or gap[dst] > -1 or not pool[src]:
                break
            v = pool[src].pop(0)
            move.append((int(v), dst))
            gap[src] -= 1
            gap[dst] += 1
        return Plan(swap, move)


class Planner:
    def __init__(self, name: str, forecast: ForecastFn):
        self.name = name
        self.forecast = forecast
        self.window = LogWindow(config.decide()["planner"]["margin_lookback_days"])

    def plan(self, obs: Observation) -> Plan:
        p, c = config.decide()["planner"], config.decide()["costs"]
        Z = obs.grid * obs.grid
        self.window.update(obs.logs, obs.day_index)
        rides = self.window.rides()
        margin = (rides["revenue"].mean() if len(rides) else 4.0) - c["ride_variable_cost_eur"]
        demand = np.maximum(self.forecast(obs, self.window), 0.0)          # (hours, Z)
        hours = obs.hour + 1 + np.arange(demand.shape[0])
        arrivals = np.zeros_like(demand)
        if len(rides):
            days = max(1, rides["day"].nunique())
            per = rides.groupby(["hour", "end"]).size() / days
            for i, h in enumerate(hours):
                if h in per.index.get_level_values(0):
                    s_ = per.loc[h]
                    arrivals[i, s_.index.to_numpy()] = s_.to_numpy()
        arrivals *= config.decide()["planner"].get("arrival_weight", 1.0)
        cum = np.cumsum(demand - arrivals, axis=0)
        peak_t = np.argmax(cum, axis=0)
        need = np.maximum(cum[peak_t, np.arange(Z)], 0.0)
        cd, ca = np.cumsum(demand, axis=0), np.cumsum(arrivals, axis=0)
        sd = np.sqrt(cd[peak_t, np.arange(Z)] + ca[peak_t, np.arange(Z)]) + 0.5

        def mv(z: int, k: float) -> float:
            """Value of the next scooter in zone z when it already has k effective scooters."""
            return margin * float(norm.sf((k + 0.5 - need[z]) / sd[z]))

        b = obs.vehicle_battery
        k = effective_supply(obs, Z)
        w = np.where(b >= p["low_battery_pct"], 1.0, np.where(b >= p["rentable_battery_pct"], p["low_battery_weight"], 0.0))
        cand = np.where(w < 1.0)[0]
        swap: list[int] = []

        def swap_value(u: int) -> float:
            # energy put into the fleet, worth more where a rentable scooter is short right now
            z = obs.vehicle_zone[u]
            return (100.0 - b[u]) / 100.0 * (1.0 + mv(z, k[z]) / margin)

        gains = np.array([swap_value(v) for v in cand])
        taken = np.zeros(len(cand), bool)
        for _ in range(min(obs.swaps, len(cand))):
            i = int(np.argmax(np.where(taken, -1, gains)))
            if taken[i] or gains[i] <= 0:
                break
            v = int(cand[i])
            taken[i] = True
            swap.append(v)
            z = obs.vehicle_zone[v]
            k[z] += 1 - w[v]
            same = (~taken) & (obs.vehicle_zone[cand] == z)
            gains[same] = [swap_value(u) for u in cand[same]]
        battery_after = b.copy()
        battery_after[swap] = 100.0
        movable = {z: sorted(np.where((obs.vehicle_zone == z) & (battery_after >= p["low_battery_pct"]))[0].tolist(),
                             key=lambda v: -battery_after[v]) for z in range(Z)}
        gain = np.array([mv(z, k[z]) for z in range(Z)])
        loss = np.array([mv(z, k[z] - 1) if movable[z] else np.inf for z in range(Z)])
        move: list[tuple[int, int]] = []
        for _ in range(obs.moves):
            dst, src = int(np.argmax(gain)), int(np.argmin(loss))
            if src == dst or gain[dst] - loss[src] <= c["move_cost_eur"] * p.get("move_cost_weight", 1.0):
                break
            v = movable[src].pop(0)
            move.append((int(v), dst))
            k[src] -= 1
            k[dst] += 1
            gain[dst], gain[src] = mv(dst, k[dst]), mv(src, k[src])
            loss[dst] = mv(dst, k[dst] - 1)
            loss[src] = mv(src, k[src] - 1) if movable[src] else np.inf
        return Plan(swap, move)
