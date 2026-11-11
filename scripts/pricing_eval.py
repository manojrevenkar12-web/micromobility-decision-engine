"""Price experiments and a price policy -> reports/<city>/pricing.json.

dev:
  1. Design check: a +20% price change measured by a rider-level A/B test and by a switchback, ten times
     each, against the truth (the same people with everyone at each price).
  2. Elasticity switchback with four price levels; per time band, the level with the highest contribution
     that keeps at least 92% of base rides becomes the price policy.
  3. The policy is validated on later weeks: its true uplift and the uplift a switchback measures.
heldout:
  the dev policy, unchanged, scored once against the base price.

    python scripts/pricing_eval.py dev
    python scripts/pricing_eval.py heldout
"""

from __future__ import annotations

import json
import sys
from datetime import date

import numpy as np
import pandas as pd

from mde import config
from mde.ops.policies import Heuristic
from mde.pricing.experiments import (
    contribution,
    estimate_switchback,
    estimate_user_ab,
    switchback_assign,
    two_prices,
    user_ab_assign,
)
from mde.pricing.policy import BandPolicy, band_of, choose_levels
from mde.world.city import build
from mde.world.sim import base_price, run

from ops_eval import HISTORY_SEED, copy_logs


def setup(name: str):
    city = build(name)
    H = (date.fromisoformat(config.world()["season"]["history_end"]) - city.days[0]).days + 1
    history = run(city, Heuristic(), 0, H, seed=HISTORY_SEED)
    return city, H, history


def go(city, history, d0, days, seed, price=base_price, arm=None):
    kw = {"arm": arm} if arm else {}
    return run(city, Heuristic(), d0, d0 + days, seed=seed, price=price,
               state=(history.final_zone.copy(), history.final_battery.copy()), logs=copy_logs(history.logs), **kw)


def new_rows(r, history, d0):
    f = r.logs.frames()
    return f["opens"][f["opens"]["day"] >= d0], f["rides"][f["rides"]["day"] >= d0]


def design_check(city, history, H) -> dict:
    p = config.decide()["pricing"]
    n = p["experiment_days"]
    rows = []
    for rep in range(p["replications"]):
        seed = 1000 + rep
        base = go(city, history, H, n, seed)
        test = go(city, history, H, n, seed, price=two_prices(p["test_multiplier"]), arm=lambda *a: 1)
        truth = float(test.daily["contribution"].mean() - base.daily["contribution"].mean())
        truth_rides = float(test.daily["rides"].mean() - base.daily["rides"].mean())
        ab = go(city, history, H, n, seed, price=two_prices(p["test_multiplier"]), arm=user_ab_assign())
        o, r = new_rows(ab, history, H)
        e_ab = estimate_user_ab(o, r, n)
        sb_arm = switchback_assign(seed, p["switchback_hours"], len(city.days))
        sb = go(city, history, H, n, seed, price=two_prices(p["test_multiplier"]), arm=sb_arm)
        _, r = new_rows(sb, history, H)
        e_sb = estimate_switchback(r, sb_arm.table, H, n, p["switchback_hours"], p["burn_in_hours"])
        rows.append({"rep": rep, "truth": truth, "truth_rides": truth_rides, "user_ab": e_ab.effect_per_day,
                     "switchback": e_sb.effect_per_day, "user_ab_rides": e_ab.rides_effect_per_day,
                     "switchback_rides": e_sb.rides_effect_per_day,
                     "base_contribution": float(base.daily["contribution"].mean())})
        print(f"  rep {rep}: truth {truth:+.0f}  user A/B {e_ab.effect_per_day:+.0f}  switchback {e_sb.effect_per_day:+.0f}",
              flush=True)
    d = pd.DataFrame(rows)
    out = {"replications": rows, "test_multiplier": p["test_multiplier"], "days": n}
    for k in ("user_ab", "switchback"):
        err = d[k] - d["truth"]
        out[k] = {"bias": float(err.mean()), "sd": float(d[k].std()), "rmse": float(np.sqrt((err**2).mean())),
                  "sign_correct": float((np.sign(d[k]) == np.sign(d["truth"])).mean())}
    out["truth"] = {"mean": float(d["truth"].mean()), "sd": float(d["truth"].std()),
                    "relative": float(d["truth"].mean() / d["base_contribution"].mean())}
    return out


def elasticity(city, history, H) -> tuple[dict, dict]:
    p = config.decide()["pricing"]
    levels = p["levels"]
    n = p["experiment_days"]
    arm = switchback_assign(77, p["switchback_hours"], len(city.days), arms=len(levels))
    r = go(city, history, H, n, 5000, price=lambda z, d, h, a: levels[a], arm=arm)
    _, rides = new_rows(r, history, H)
    hours = pd.DataFrame([(d, h) for d in range(H, H + n) for h in range(24)], columns=["day", "hour"])
    hours["level"] = [arm.table[(d, h // p["switchback_hours"])] for d, h in zip(hours["day"], hours["hour"], strict=True)]
    hours = hours[(hours["hour"] % p["switchback_hours"]) >= p["burn_in_hours"]]
    agg = rides.assign(c=contribution(rides)).groupby(["day", "hour"]).agg(c=("c", "sum"), n=("c", "size"))
    hours = hours.join(agg, on=["day", "hour"]).fillna(0.0)
    hours["band"] = [band_of(city.days[d], h) for d, h in zip(hours["day"], hours["hour"], strict=True)]
    chosen, table = choose_levels(hours, levels)
    return chosen, table


def validate(city, history, d0, days, policy: BandPolicy, seeds) -> dict:
    p = config.decide()["pricing"]
    true_diff, true_rides, est = [], [], []
    for s in seeds:
        base = go(city, history, d0, days, s)
        pol = go(city, history, d0, days, s, price=policy.price(city.days))
        true_diff.append(float(pol.daily["contribution"].mean() - base.daily["contribution"].mean()))
        true_rides.append(float(pol.daily["rides"].mean() / base.daily["rides"].mean() - 1))
        base_c = float(base.daily["contribution"].mean())
        arm = switchback_assign(s + 9, p["switchback_hours"], len(city.days))
        policy_price = policy.price(city.days)

        def alternate(z, d, h, a, f=policy_price):
            return f(z, d, h, 1) if a else 1.0

        sb = go(city, history, d0, days, s, price=alternate, arm=arm)
        _, r = new_rows(sb, history, d0)
        est.append(estimate_switchback(r, arm.table, d0, days, p["switchback_hours"], p["burn_in_hours"]).effect_per_day)
    return {"true_uplift_per_day": float(np.mean(true_diff)), "true_uplift_relative": float(np.mean(true_diff) / base_c),
            "true_rides_change": float(np.mean(true_rides)), "switchback_estimate_per_day": float(np.mean(est)),
            "per_seed": {"true": true_diff, "switchback": est}}


def main(name: str) -> None:
    city, H, history = setup(name)
    n = config.decide()["pricing"]["experiment_days"]
    seeds = config.decide()["eval"]["seeds"]
    path = config.REPORTS / name
    path.mkdir(parents=True, exist_ok=True)
    if name == "dev":
        design = design_check(city, history, H)
        chosen, table = elasticity(city, history, H)
        policy = BandPolicy(chosen)
        val = validate(city, history, H + n, len(city.days) - H - n, policy, seeds)
        out = {"city": name, "design": design, "elasticity_table": table, "policy": chosen, "validation": val}
        (config.REPORTS / "pricing_policy.json").write_text(json.dumps(chosen, indent=1))
    else:
        chosen = json.loads((config.REPORTS / "pricing_policy.json").read_text())
        val = validate(city, history, H, len(city.days) - H, BandPolicy(chosen), seeds)
        out = {"city": name, "policy": chosen, "validation": val}
    (path / "pricing.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k not in ("elasticity_table",)}, indent=1, default=str)[:3000])


if __name__ == "__main__":
    main(sys.argv[1])
