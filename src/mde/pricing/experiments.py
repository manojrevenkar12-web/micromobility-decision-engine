"""Price experiments on a shared fleet, and why the design matters.

Riders in a price test share the same scooters. If half the riders see a higher price, fewer of them ride,
which leaves more scooters for the other half: the control group does better than it would in a world
without the test, and a rider-level A/B test overstates what a city-wide price change does.

user_ab      each app open is randomised to the test price or the base price (the usual product A/B)
switchback   the whole city switches between the prices in randomised 2-hour windows; the first hour of
             each window is dropped so scooters freed in one window do not count in the next; arms are
             compared within the same hour of day

The truth for a design comparison comes from the simulator: the same people with everyone at the base
price and everyone at the test price. Only the evaluation reads it.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from mde import config


def contribution(rides: pd.DataFrame) -> pd.Series:
    return rides["revenue"] - config.decide()["costs"]["ride_variable_cost_eur"]


def user_ab_assign(p: float = 0.5):
    def arm(zone: int, day: int, hour: int, rng: np.random.Generator) -> int:
        return int(rng.random() < p)

    return arm


def switchback_assign(seed: int, window_hours: int, n_days: int, arms: int = 2):
    """City-wide arm per (day, window), drawn up front so the analysis knows every window's arm."""
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, arms, size=(n_days, 24 // window_hours))
    table = {(d, w): int(draws[d, w]) for d in range(n_days) for w in range(24 // window_hours)}

    def arm(zone: int, day: int, hour: int, _rng: np.random.Generator) -> int:
        return table[(day, hour // window_hours)]

    arm.table = table
    return arm


def two_prices(test: float):
    base = config.decide()["pricing"].get("base", 1.0)

    def price(zone: int, day: int, hour: int, arm: int) -> float:
        return test if arm == 1 else base

    return price


@dataclass
class Estimate:
    effect_per_day: float      # contribution EUR per day if every rider saw the test price
    rides_effect_per_day: float


def estimate_user_ab(opens: pd.DataFrame, rides: pd.DataFrame, n_days: int) -> Estimate:
    """Per-open contribution in each arm, scaled to all opens: the textbook rider-level estimate."""
    o = opens.groupby("arm").size()
    c = contribution(rides).groupby(rides["arm"]).sum()
    n = rides.groupby("arm").size()
    per_open = c / o
    rides_per_open = n / o
    total_opens = o.sum() / n_days
    return Estimate(float((per_open[1] - per_open[0]) * total_opens),
                    float((rides_per_open[1] - rides_per_open[0]) * total_opens))


def fixed_effects(df: pd.DataFrame, y: str, arm_col: str = "arm", covariates: tuple[str, ...] = ()) -> dict:
    """OLS of an hourly outcome on day and hour-of-day fixed effects plus one dummy per arm level (> 0).

    Day effects absorb weather and weekday, hour effects the daily cycle, so the arm effect is estimated
    from hours of the same day and the same hour of other days. Covariates must be ones the price cannot
    move. Hourly app opens and rentable scooters both looked like CUPED candidates and both bias the estimate
    here, because a price changes how many scooters are left and so who finds one (docs/decisions.md).
    Returns {level: effect per hour}.
    """
    days = pd.get_dummies(df["day"], prefix="d", dtype=float)
    hours = pd.get_dummies(df["hour"], prefix="h", drop_first=True, dtype=float)
    arms = pd.get_dummies(df[arm_col], prefix="a", dtype=float)
    levels = sorted(df[arm_col].unique())
    arms = arms.drop(columns=f"a_{levels[0]}")
    cov = df[list(covariates)].astype(float) if covariates else pd.DataFrame(index=df.index)
    cov = cov - cov.mean()
    X = pd.concat([days, hours, cov, arms], axis=1).to_numpy()
    beta, *_ = np.linalg.lstsq(X, df[y].to_numpy(float), rcond=None)
    k = arms.shape[1]
    return {lv: float(b) for lv, b in zip(levels[1:], beta[-k:], strict=True)}


def estimate_switchback(rides: pd.DataFrame, arm_of: dict, d_from: int, n_days: int, window: int, burn_in: int) -> Estimate:
    """Hour-level contribution by arm with day and hour fixed effects, burn-in hours dropped."""
    hours = pd.DataFrame([(d, h) for d in range(d_from, d_from + n_days) for h in range(24)], columns=["day", "hour"])
    hours["arm"] = [arm_of[(d, h // window)] for d, h in zip(hours["day"], hours["hour"], strict=True)]
    hours = hours[(hours["hour"] % window) >= burn_in]
    r = rides.assign(c=contribution(rides))
    agg = r.groupby(["day", "hour"]).agg(c=("c", "sum"), n=("c", "size"))
    hours = hours.join(agg, on=["day", "hour"]).fillna(0.0)
    return Estimate(fixed_effects(hours, "c")[1] * 24, fixed_effects(hours, "n")[1] * 24)
