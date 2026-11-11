"""The simulator's invariants and the decision code's contracts."""

import re
from pathlib import Path

import numpy as np
import pandas as pd

from mde.causal.did import did
from mde.demand.censoring import zone_hour_table
from mde.ops.policies import Heuristic, Planner
from mde.pricing.experiments import fixed_effects, switchback_assign
from mde.world.city import build
from mde.world.sim import Plan, run

ROOT = Path(__file__).resolve().parents[1]
CITY = build("dev")


class Idle:
    name = "idle"

    def plan(self, obs):
        return Plan()


def test_decision_code_never_reads_the_truth():
    banned = re.compile(r"mde\.world\.(city|imu)|mde\.evals\.oracle|config\.world\(\)")
    for folder in ("demand", "ops", "pricing", "causal", "sensing"):
        for p in (ROOT / "src" / "mde" / folder).glob("*.py"):
            assert not banned.search(p.read_text()), p


def test_fleet_is_conserved_and_rides_need_a_charged_scooter():
    r = run(CITY, Heuristic(), 0, 3, seed=1)
    assert len(r.final_zone) == CITY.fleet
    rides = r.logs.frames()["rides"]
    assert len(rides) > 0 and (rides["battery_used"] > 0).all()
    assert (r.final_battery >= 0).all() and (r.final_battery <= 100).all()


def test_same_seed_same_people_whatever_the_policy_or_price():
    a = run(CITY, Idle(), 0, 2, seed=5)
    b = run(CITY, Heuristic(), 0, 2, seed=5, price=lambda z, d, h, arm: 1.3)
    assert (a.daily["intents"].to_numpy() == b.daily["intents"].to_numpy()).all()
    assert b.daily["rides"].sum() < a.daily["rides"].sum() * 1.2


def test_ops_respect_crew_capacity():
    r = run(CITY, Heuristic(), 0, 2, seed=2)
    ops = r.logs.frames()["ops"]
    per_shift = ops.groupby(["day", "hour", "kind"]).size()
    assert per_shift.max() <= 90


def test_planner_plans_within_capacity_with_any_forecast():
    flat = Planner("flat", lambda obs, w: np.full((6, CITY.Z), 0.5))
    hist = run(CITY, Heuristic(), 0, 2, seed=3)
    r = run(CITY, flat, 2, 3, seed=3, state=(hist.final_zone, hist.final_battery), logs=hist.logs)
    ops = pd.DataFrame(r.logs.ops, columns=["day", "hour", "kind", "v", "f", "t"])
    ops = ops[ops["day"] == 2]
    assert (ops.groupby(["hour", "kind"]).size() <= 90).all()
    assert ops["t"].between(0, CITY.Z - 1).all()


def test_censoring_correction_counts_opens_that_found_nothing():
    opens = pd.DataFrame({"day": 0, "hour": 8, "zone": 0, "nearby": [True] * 10 + [False] * 10,
                          "multiplier": 1.0, "arm": 0, "rented": [True] * 5 + [False] * 5 + [False] * 10})
    rides = pd.DataFrame({"day": [0] * 5, "hour": 8, "start": 0, "end": 1, "minutes": 10, "revenue": 3,
                          "battery_used": 4, "arm": 0, "multiplier": 1.0})
    t = zone_hour_table(opens, rides, 1, 2)
    row = t[(t["hour"] == 8) & (t["zone"] == 0)].iloc[0]
    assert row["demand_naive"] == 5
    assert 9.0 < row["demand_corrected"] <= 10.0   # 20 opens x ~0.5 conversion


def test_fixed_effects_recover_a_known_effect():
    rng = np.random.default_rng(0)
    rows = []
    for d in range(30):
        day_fx = rng.normal(0, 20)
        for h in range(24):
            arm = int(rng.random() < 0.5)
            rows.append((d, h, arm, 50 + day_fx + 10 * np.sin(h / 3) + 7 * arm + rng.normal(0, 3)))
    df = pd.DataFrame(rows, columns=["day", "hour", "arm", "c"])
    assert abs(fixed_effects(df, "c")[1] - 7) < 1.0


def test_switchback_arms_are_fixed_per_window():
    arm = switchback_assign(1, 2, 10)
    assert arm(0, 3, 4, None) == arm(99, 3, 5, None)
    assert {arm(0, d, h, None) for d in range(10) for h in range(24)} == {0, 1}


def test_did_recovers_a_known_effect():
    rng = np.random.default_rng(1)
    rows = []
    for z in range(40):
        treated = z < 15
        base = rng.uniform(20, 60)
        for d in range(60):
            post = d >= 30
            season = 1 + 0.01 * d
            y = base * season * (0.8 if treated and post else 1.0) * rng.lognormal(0, 0.05)
            rows.append((z, d, treated, post, y))
    p = pd.DataFrame(rows, columns=["zone", "day", "treated", "post", "y"])
    r = did(p, "y", n_boot=100)
    assert abs(r["effect"] + 0.2) < 0.03 and r["lo"] < -0.2 < r["hi"]
