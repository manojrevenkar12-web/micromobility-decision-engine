"""Dashboard data (web/public/data/summary.json) and the README tables, from the generated reports.

The only thing computed here is the hero map: one July weekday of the dev city under the status-quo
heuristic, re-simulated to show where people found no scooter, hour by hour.
"""

from __future__ import annotations

import json
from datetime import date

import numpy as np

from mde import config
from mde.ops.policies import Heuristic
from mde.world.city import build
from mde.world.sim import run

from ops_eval import HISTORY_SEED, copy_logs

R = config.REPORTS
WEB = config.ROOT / "web" / "public" / "data"


def read(path):
    p = R / path
    return json.loads(p.read_text()) if p.exists() else None


def hero_day() -> dict:
    city = build("dev")
    H = (date.fromisoformat(config.world()["season"]["history_end"]) - city.days[0]).days + 1
    hist = run(city, Heuristic(), 0, H, seed=HISTORY_SEED)
    d = H + 1  # Wednesday 2 July 2025
    r = run(city, Heuristic(), H, d + 1, seed=101, state=(hist.final_zone, hist.final_battery), logs=copy_logs(hist.logs))
    f = r.logs.frames()
    o, rides = f["opens"][f["opens"]["day"] == d], f["rides"][f["rides"]["day"] == d]
    lost = np.zeros((24, city.Z), int)
    for (h, z), n in o[o["multiplier"].isna()].groupby(["hour", "zone"]).size().items():
        lost[h, z] = n
    starts = np.zeros((24, city.Z), int)
    for (h, z), n in rides.groupby(["hour", "start"]).size().items():
        starts[h, z] = n
    return {"date": city.days[d].isoformat(), "grid": city.grid, "available": r.logs.available[d].tolist(),
            "lost": lost.tolist(), "rides": starts.tolist(), "zone_type": city.zone_type.tolist(),
            "totals": {"rides": int(len(rides)), "lost_opens": int(lost.sum()), "fleet": city.fleet}}


def slim_ops(o):
    if not o:
        return None
    return {k: o[k] for k in ("city", "fleet", "zones", "history_days", "eval_days", "seeds", "policies", "forecast")}


def main() -> None:
    dev_ops, held_ops = read("dev/ops.json"), read("heldout/ops.json")
    dev_pr, held_pr = read("dev/pricing.json"), read("heldout/pricing.json")
    causal, gate = read("dev/causal.json"), read("dev/gate.json")
    s_dev, s_held = read("sensing_dev.json"), read("sensing_heldout.json")
    summary = {
        "generated": date.today().isoformat(),
        "hero": hero_day(),
        "ops": {"dev": slim_ops(dev_ops), "heldout": slim_ops(held_ops)},
        "pricing": {"dev": dev_pr and {k: dev_pr[k] for k in ("design", "policy", "validation", "elasticity_table")},
                    "heldout": held_pr and {k: held_pr[k] for k in ("policy", "validation")}},
        "causal": causal,
        "sensing": {"dev": s_dev and {k: v for k, v in s_dev.items() if k != "train_loss"}, "heldout": s_held},
        "gate": gate,
    }
    WEB.mkdir(parents=True, exist_ok=True)
    (WEB / "summary.json").write_text(json.dumps(summary, separators=(",", ":")))
    tables(summary)


def tables(s) -> None:
    for split in ("heldout", "dev"):
        o = s["ops"][split]
        if not o:
            continue
        print(f"\n### Operations, {split} city ({o['eval_days']} days x {len(o['seeds'])} seeds, fleet {o['fleet']})\n")
        print("| Policy | Contribution / day | Rides / day | Served share of demand | vs heuristic, 95% interval |")
        print("|---|---|---|---|---|")
        for k, v in o["policies"].items():
            c = v["vs_heuristic"]
            ci = "—" if k == "heuristic" else f"{c['mean']:+.0f} € ({c['lo']:+.0f} to {c['hi']:+.0f})"
            print(f"| {k} | {v['contribution_per_day']:,.0f} € | {v['rides_per_day']:,.0f} | {v['served_share']:.1%} | {ci} |")
        f = o["forecast"]
        print(f"\nForecast WAPE (zone x 6 h): censored {f['naive']['wape_zone_6h']:.1%} (bias {f['naive']['bias']:+.1%}), "
              f"corrected {f['corrected']['wape_zone_6h']:.1%} (bias {f['corrected']['bias']:+.1%}). Observed rides were "
              f"{f['censoring']['observed_rides_share_of_demand']:.1%} of true demand; the correction recovers "
              f"{f['censoring']['corrected_share_of_demand']:.1%}.")
    p = s["pricing"]["dev"]
    if p:
        d = p["design"]
        print(f"\n### Price experiments (dev, {len(d['replications'])} x {d['days']} days, +20% price)\n")
        print(f"True effect {d['truth']['mean']:+.0f} €/day ({d['truth']['relative']:+.1%}).")
        print("| Design | Bias €/day | SD €/day | RMSE €/day |\n|---|---|---|---|")
        for k in ("user_ab", "switchback"):
            print(f"| {k} | {d[k]['bias']:+.0f} | {d[k]['sd']:.0f} | {d[k]['rmse']:.0f} |")
        for split in ("dev", "heldout"):
            v = s["pricing"][split] and s["pricing"][split]["validation"]
            if v:
                print(f"\nPolicy {s['pricing'][split]['policy']} on {split}: true uplift {v['true_uplift_per_day']:+.0f} €/day "
                      f"({v['true_uplift_relative']:+.1%}), rides {v['true_rides_change']:+.1%}; switchback per seed "
                      f"{[round(x) for x in v['per_seed']['switchback']]}")
    c = s["causal"]
    if c:
        print(f"\n### Competitor launch (truth {c['truth']:+.0%})\n")
        for y in ("rides", "demand_corrected"):
            dd = c[y]["did"]
            print(f"- {y}: naive pre/post {c[y]['naive_pre_post']:+.1%}; "
                  f"DiD {dd['effect']:+.1%} ({dd['lo']:+.1%} to {dd['hi']:+.1%})")
    for split in ("dev", "heldout"):
        x = s["sensing"][split]
        if x:
            print(f"\n### Sensing, {split} ({x['hardware']})\n")
            print(json.dumps({"windows": x["windows"], "rides": x["rides"], "edge": x.get("edge")}, indent=1))
    if s["gate"]:
        print("\n### Gate\n")
        print(json.dumps(s["gate"]["decisions"], indent=1))


if __name__ == "__main__":
    main()
