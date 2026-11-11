"""Hour-by-hour simulation of a scooter fleet in a City.

People with an intent to ride appear in a zone; they rent the nearest rentable scooter (their zone, or a
neighbouring one if they walk), accept or refuse the price, ride to a destination and leave the scooter
there with less battery. Twice a day an operations policy swaps batteries and moves scooters.

Only `Observation` and the logs leave this module; the City's true intents stay inside.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Protocol

import numpy as np
import pandas as pd

from mde import config
from mde.world.city import City


@dataclass
class Observation:
    """What an operator knows at planning time."""

    day: date
    day_index: int
    hour: int
    grid: int
    xy: np.ndarray
    vehicle_zone: np.ndarray
    vehicle_battery: np.ndarray
    swaps: int
    moves: int
    rain_hours_today: np.ndarray
    temp_today: float
    logs: Logs


@dataclass
class Plan:
    swap: list[int] = field(default_factory=list)                 # vehicle ids to get a fresh battery
    move: list[tuple[int, int]] = field(default_factory=list)     # (vehicle id, destination zone)


class Policy(Protocol):
    name: str

    def plan(self, obs: Observation) -> Plan: ...


PriceFn = Callable[[int, int, int, int], float]   # (zone, day_index, hour, arm) -> multiplier
ArmFn = Callable[[int, int, int, np.random.Generator], int]   # (zone, day_index, hour, rng) -> arm


@dataclass
class Logs:
    opens: list = field(default_factory=list)      # (day, hour, zone, nearby, shown_multiplier, arm, rented)
    rides: list = field(default_factory=list)      # (day, hour, start, end, minutes, revenue, battery_used, arm, mult)
    ops: list = field(default_factory=list)        # (day, hour, kind, vehicle, from_zone, to_zone)
    weather: dict = field(default_factory=dict)    # day -> (rain by hour, temperature): observed, also forecast
    available: np.ndarray | None = None            # (D, 24, Z) rentable scooters at the start of each hour

    def frames(self) -> dict[str, pd.DataFrame]:
        return {
            "opens": pd.DataFrame(self.opens, columns=["day", "hour", "zone", "nearby", "multiplier", "arm", "rented"]),
            "rides": pd.DataFrame(self.rides, columns=["day", "hour", "start", "end", "minutes", "revenue",
                                                       "battery_used", "arm", "multiplier"]),
            "ops": pd.DataFrame(self.ops, columns=["day", "hour", "kind", "vehicle", "from_zone", "to_zone"]),
            "weather": pd.DataFrame([(d, h, bool(r[h]), t) for d, (r, t) in sorted(self.weather.items()) for h in range(24)],
                                    columns=["day", "hour", "rain", "temp"]),
        }


def base_price(zone: int, day: int, hour: int, arm: int) -> float:
    return config.world()["pricing"]["base_multiplier"]


def no_experiment(zone: int, day: int, hour: int, rng: np.random.Generator) -> int:
    return 0


@dataclass
class Result:
    logs: Logs
    daily: pd.DataFrame          # per day: rides, revenue, ops cost, contribution, intents (truth), lost
    final_zone: np.ndarray
    final_battery: np.ndarray


def initial_fleet(city: City, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    w = city.intents[: 7].mean(axis=(0, 1))
    zone = rng.choice(city.Z, size=city.fleet, p=w / w.sum())
    battery = rng.uniform(40, 100, size=city.fleet)
    return zone, battery


def run(city: City, policy: Policy, d_from: int, d_to: int, seed: int,
        price: PriceFn = base_price, arm: ArmFn = no_experiment,
        state: tuple[np.ndarray, np.ndarray] | None = None, logs: Logs | None = None) -> Result:
    """Simulate days [d_from, d_to). Common random numbers: the same seed gives the same people."""
    w = config.world()
    tr, rd, op = w["trips"], w["riders"], w["ops"]
    rng_people = np.random.default_rng([city.seed, seed, 1])
    rng_choice = np.random.default_rng([city.seed, seed, 2])
    rng_arm = np.random.default_rng([city.seed, seed, 3])
    zone, battery = state if state else initial_fleet(city, np.random.default_rng([city.seed, seed, 0]))
    zone, battery = zone.copy(), battery.copy()
    logs = logs or Logs()
    if logs.available is None:
        logs.available = np.zeros((len(city.days), 24, city.Z), np.int32)
    min_b = tr["min_rentable_battery"]
    daily = []
    for d in range(d_from, d_to):
        day = city.days[d]
        wk = day.weekday() < 5
        rev_day = cost_day = 0.0
        rides_day = intents_day = 0
        logs.weather[d] = (city.rain_hours[d].copy(), float(city.temp_c[d]))
        for h in range(24):
            if h in (op["night_hour"], op["midday_hour"]):
                night = h == op["night_hour"]
                obs = Observation(day, d, h, city.grid, city.xy, zone.copy(), battery.copy(),
                                  op["swaps_per_night"] if night else op["swaps_midday"],
                                  op["moves_per_night"] if night else op["moves_midday"],
                                  city.rain_hours[d].copy(), float(city.temp_c[d]), logs)
                plan = policy.plan(obs)
                for v in plan.swap[: obs.swaps]:
                    battery[v] = 100.0
                    cost_day += op["swap_cost_eur"]
                    logs.ops.append((d, h, "swap", v, zone[v], zone[v]))
                for v, to in plan.move[: obs.moves]:
                    logs.ops.append((d, h, "move", v, zone[v], to))
                    zone[v] = to
                    cost_day += op["move_cost_eur"]
            rentable = battery >= min_b
            by_zone: list[list[int]] = [[] for _ in range(city.Z)]
            for v in np.where(rentable)[0]:
                by_zone[zone[v]].append(int(v))
            logs.available[d, h] = [len(b) for b in by_zone]
            n = rng_people.poisson(city.intents[d, h])
            intents_day += int(n.sum())
            attract = city.attraction(h, wk)
            order = np.repeat(np.arange(city.Z), n)
            rng_people.shuffle(order)
            for z in order:
                z = int(z)
                commuter = rng_people.random() < city.commuter_share[d, h]
                walk = rng_people.random() < rd["walk_to_neighbour_prob"]
                u_open, u_accept, u_dest = rng_people.random(3)
                a = arm(z, d, h, rng_arm)
                src = z if by_zone[z] else -1
                if src < 0 and walk:
                    cands = [nb for nb in city.neighbours[z] if by_zone[nb]]
                    if cands:
                        src = int(cands[int(u_dest * len(cands))])
                nearby = bool(by_zone[z])
                if src < 0:
                    if u_open < rd["open_if_none_prob"]:
                        logs.opens.append((d, h, z, nearby, np.nan, a, False))
                    continue
                m = price(src, d, h, a)
                b = rd["commuter_b"] if commuter else rd["leisure_b"]
                p_accept = 1 / (1 + np.exp(-(rd["accept_a"] - b * np.log(m))))
                rented = u_accept < p_accept
                logs.opens.append((d, h, z, nearby, m, a, rented))
                if not rented:
                    continue
                vlist = by_zone[src]
                v = vlist.pop(int(rng_choice.integers(len(vlist))))
                p = attract * np.exp(-city.km[src] / tr["mean_km_decay"])
                dest = int(np.searchsorted(np.cumsum(p / p.sum()), u_dest * 0.999999))
                km = float(city.km[src, dest]) * (1 + 0.25 * rng_choice.random())
                minutes = km / tr["speed_kmh"] * 60 + 2 + rng_choice.exponential(2)
                used = km * tr["battery_pct_per_km"] + 0.3
                revenue = (tr["unlock_eur"] + tr["per_min_eur"] * minutes) * m
                zone[v], battery[v] = dest, max(0.0, battery[v] - used)
                rev_day += revenue
                cost_day += tr["variable_cost_per_ride_eur"]
                rides_day += 1
                logs.rides.append((d, h, src, dest, round(minutes, 2), round(revenue, 4), round(used, 3), a, m))
        daily.append({"day": d, "date": day.isoformat(), "rides": rides_day, "revenue": rev_day, "cost": cost_day,
                      "contribution": rev_day - cost_day, "intents": intents_day})
    return Result(logs, pd.DataFrame(daily), zone, battery)
