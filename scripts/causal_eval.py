"""Quasi-experiment on the dev city's history: what did the competitor launch do to demand?

    python scripts/causal_eval.py   -> reports/dev/causal.json
"""

from __future__ import annotations

import json
from datetime import date

from mde import config
from mde.causal.did import did, event_study, naive_pre_post
from mde.demand.censoring import zone_hour_table
from mde.ops.policies import Heuristic
from mde.world.city import build
from mde.world.sim import run

from ops_eval import HISTORY_SEED


def main() -> None:
    city = build("dev")
    H = (date.fromisoformat(config.world()["season"]["history_end"]) - city.days[0]).days + 1
    hist = run(city, Heuristic(), 0, H, seed=HISTORY_SEED)
    f = hist.logs.frames()
    t = zone_hour_table(f["opens"], f["rides"], H, city.Z)
    panel = t.groupby(["zone", "day"])[["rides", "demand_corrected", "opens"]].sum().reset_index()
    c = config.decide()["did"]
    event = (date.fromisoformat(c["event_date"]) - city.days[0]).days
    panel["treated"] = city.xy[panel["zone"], 0] >= c["treated_x_from"]
    panel["post"] = panel["day"] >= event
    out = {"event_day": event, "treated_zones": int(panel.groupby("zone")["treated"].first().sum()),
           "truth": config.world()["events"]["competitor"]["effect"]}
    for y in ("rides", "demand_corrected"):
        out[y] = {"naive_pre_post": naive_pre_post(panel, y), "did": did(panel, y), "event_study": event_study(panel, y, event)}
    config.REPORTS.joinpath("dev").mkdir(parents=True, exist_ok=True)
    (config.REPORTS / "dev" / "causal.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if kk != "event_study"})
                      for k, v in out.items()}, indent=1))


if __name__ == "__main__":
    main()
