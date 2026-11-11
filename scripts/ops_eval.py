"""Forecasts and operations policies for one city -> reports/<city>/ops.json.

1. Apr-Jun is operated by the status-quo heuristic; its logs are all the models learn from.
2. Two forecasters are trained: on observed rides (censored) and on demand corrected with app opens.
3. Jul-Aug is run again under each policy with the same people (common random numbers, three seeds),
   starting from the same fleet state, and the policies are compared day by day.

    python scripts/ops_eval.py dev        # every choice is made here
    python scripts/ops_eval.py heldout    # once, see docs/heldout.md
"""

from __future__ import annotations

import json
import sys
import time
from datetime import date

import numpy as np
import pandas as pd

from mde import config
from mde.demand.censoring import zone_hour_table
from mde.demand.forecast import Forecaster, add_recent
from mde.demand.online import forecast_fn
from mde.evals.oracle import oracle_forecast, unconstrained
from mde.evals.stats import block_bootstrap_ci, wape
from mde.ops.policies import Heuristic, Planner
from mde.world.city import build
from mde.world.sim import Logs, run

HISTORY_SEED = 7


def copy_logs(logs: Logs) -> Logs:
    return Logs(list(logs.opens), list(logs.rides), list(logs.ops), dict(logs.weather), logs.available.copy())


def forecast_accuracy(city, history, models, follow) -> dict:
    """Score both forecasts against the true unconstrained demand on Jul-Aug, at the planner's grain."""
    H = len(history.daily)
    f_all = {k: pd.concat([history.logs.frames()[k], follow.logs.frames()[k]]) for k in ("opens", "rides", "weather")}
    f_all["weather"] = f_all["weather"].drop_duplicates(["day", "hour"])
    n = len(city.days)
    table = zone_hour_table(f_all["opens"], f_all["rides"], n, city.Z)
    truth = unconstrained(city)
    out = {}
    for name, m in models.items():
        t = m.frame(add_recent(table, m.target), f_all["weather"])
        t = t[t["day"] >= H]
        pred = m.model.predict(t[[c for c in m.model.feature_name_]])
        tv = truth[t["day"].to_numpy(), t["hour"].to_numpy(), t["zone"].to_numpy()]
        win = (t["hour"] // config.decide()["planner"]["horizon_hours"]).to_numpy()
        key = pd.MultiIndex.from_arrays([t["day"], win, t["zone"]])
        p6 = pd.Series(pred, index=key).groupby(level=[0, 1, 2]).sum()
        t6 = pd.Series(tv, index=key).groupby(level=[0, 1, 2]).sum()
        out[name] = {"wape_zone_6h": wape(p6.to_numpy(), t6.to_numpy()), "bias": float(pred.sum() / tv.sum() - 1)}
    hist_truth = truth[:H].sum()
    out["censoring"] = {
        "observed_rides_share_of_demand": float(history.daily["rides"].sum() / hist_truth),
        "corrected_share_of_demand": float(zone_hour_table(*[history.logs.frames()[k] for k in ("opens", "rides")], H,
                                                           city.Z)["demand_corrected"].sum() / hist_truth),
    }
    return out


def main(name: str) -> None:
    t0 = time.time()
    city = build(name)
    s = config.world()["season"]
    H = (date.fromisoformat(s["history_end"]) - city.days[0]).days + 1
    end = len(city.days)
    history = run(city, Heuristic(), 0, H, seed=HISTORY_SEED)
    hf = history.logs.frames()
    table = zone_hour_table(hf["opens"], hf["rides"], H, city.Z)
    models = {
        "naive": Forecaster("demand_naive", city.xy, city.days[0]).fit(table, hf["weather"]),
        "corrected": Forecaster("demand_corrected", city.xy, city.days[0]).fit(table, hf["weather"]),
    }
    print(f"{name}: history {H} days, models fitted ({time.time() - t0:.0f}s)", flush=True)
    policies = {
        "heuristic": lambda: Heuristic(),
        "planner-naive": lambda: Planner("planner-naive", forecast_fn(models["naive"])),
        "planner-corrected": lambda: Planner("planner-corrected", forecast_fn(models["corrected"])),
        "planner-oracle": lambda: Planner("planner-oracle", oracle_forecast(city)),
    }
    daily = {k: [] for k in policies}
    ops_count = {k: [] for k in policies}
    follow = None
    for seed in config.decide()["eval"]["seeds"]:
        for k, make in policies.items():
            r = run(city, make(), H, end, seed=seed, state=(history.final_zone.copy(), history.final_battery.copy()),
                    logs=copy_logs(history.logs))
            d = r.daily.assign(seed=seed)
            daily[k].append(d)
            ops = pd.DataFrame(r.logs.ops[len(history.logs.ops):], columns=["day", "hour", "kind", "v", "f", "t"])
            ops_count[k].append(ops["kind"].value_counts().to_dict())
            if k == "heuristic" and follow is None:
                follow = r
            print(f"  seed {seed} {k}: {d['contribution'].mean():.0f} EUR/day, {d['rides'].mean():.0f} rides/day "
                  f"({time.time() - t0:.0f}s)", flush=True)
    ev = config.decide()["eval"]
    res = {}
    base = pd.concat(daily["heuristic"])
    for k in policies:
        d = pd.concat(daily[k])
        diff = d["contribution"].to_numpy() - base["contribution"].to_numpy()
        res[k] = {
            "contribution_per_day": float(d["contribution"].mean()),
            "contribution_per_vehicle_day": float(d["contribution"].mean() / city.fleet),
            "rides_per_day": float(d["rides"].mean()),
            "rides_per_vehicle_day": float(d["rides"].mean() / city.fleet),
            "served_share": float(d["rides"].sum() / (unconstrained(city)[H:end].sum() * len(ev["seeds"]))),
            "ops_per_day": {kk: float(np.mean([c.get(kk, 0) for c in ops_count[k]]) / (end - H)) for kk in ("swap", "move")},
            "vs_heuristic": block_bootstrap_ci(diff, ev["bootstrap"], ev["block_days"]),
        }
    accuracy = forecast_accuracy(city, history, models, follow)
    out = {"city": name, "fleet": city.fleet, "zones": city.Z, "history_days": H, "eval_days": end - H,
           "seeds": ev["seeds"], "policies": res, "forecast": accuracy,
           "daily": {k: pd.concat(v).groupby("day")[["contribution", "rides"]].mean().reset_index().to_dict("list")
                     for k, v in daily.items()}}
    path = config.REPORTS / name
    path.mkdir(parents=True, exist_ok=True)
    (path / "ops.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "ops_per_day"} for k, v in res.items()}, indent=1))
    print(json.dumps(accuracy, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
