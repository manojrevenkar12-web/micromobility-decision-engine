"""Evaluation-only access to the truth: the unconstrained demand a perfect forecast would know.

Only mde.evals and scripts that score things import this (tests/test_isolation.py).
"""

from __future__ import annotations

import numpy as np

from mde import config
from mde.world.city import City


def accept_at_base() -> float:
    r = config.world()["riders"]
    return float(1 / (1 + np.exp(-r["accept_a"])))


def unconstrained(city: City) -> np.ndarray:
    """(D, 24, Z) expected rides if a scooter were always near, at the base price."""
    return city.intents * accept_at_base()


def oracle_forecast(city: City):
    lam = unconstrained(city)
    H = config.decide()["planner"]["horizon_hours"]

    def fn(obs, window) -> np.ndarray:
        hours = [h for h in range(obs.hour + 1, obs.hour + 1 + H) if h < 24]
        return lam[obs.day_index, hours]

    return fn
