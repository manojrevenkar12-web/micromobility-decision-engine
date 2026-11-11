"""Release decisions per component from the dev-city reports -> reports/dev/gate.json."""

from __future__ import annotations

import json

from mde import config


def main() -> None:
    g = config.gate()
    R = config.REPORTS
    ops = json.loads((R / "dev" / "ops.json").read_text())
    pr = json.loads((R / "dev" / "pricing.json").read_text())
    se = json.loads((R / "sensing_dev.json").read_text())
    ca = json.loads((R / "dev" / "causal.json").read_text())
    f, d, gs = ops["forecast"], pr["design"], g["sensing"]
    max_bias = g["pricing"]["max_design_bias_share"] * abs(d["truth"]["mean"])
    did = ca["demand_corrected"]["did"]
    checks = {
        "forecast: corrected WAPE <= 0.8 x censored":
            f["corrected"]["wape_zone_6h"] <= g["forecast"]["max_wape_vs_naive"] * f["naive"]["wape_zone_6h"],
        "forecast: |bias| <= 5%": abs(f["corrected"]["bias"]) <= g["forecast"]["max_abs_bias"],
        "ops: planner beats heuristic (95% interval above zero)": ops["policies"]["planner-corrected"]["vs_heuristic"]["lo"] > 0,
        "pricing: switchback bias within 10% of the true effect": abs(d["switchback"]["bias"]) <= max_bias,
        "pricing: rider A/B bias within 10% of the true effect": abs(d["user_ab"]["bias"]) <= max_bias,
        "pricing: policy uplift confirmed by switchback": min(pr["validation"]["per_seed"]["switchback"]) > 0,
        "sensing: false slowdowns <= 1 per 100 km":
            se["rides"]["false_slowdowns_per_100km"] <= gs["max_false_slowdowns_per_100km"],
        "sensing: sidewalk stretches caught >= 85%": se["rides"]["caught_share"] >= gs["min_sidewalk_caught_share"],
        "sensing: tandem precision >= 0.85": se["windows"]["tandem_precision"] >= gs["min_tandem_precision"],
        "sensing: int8 agrees with float >= 99%": se["edge"]["int8_top1_agreement"] >= gs["min_int8_agreement"],
        "causal: DiD on corrected demand covers the truth": did["lo"] <= ca["truth"] <= did["hi"],
    }
    decisions = {
        "forecast": "ship" if all(v for k, v in checks.items() if k.startswith("forecast")) else "hold",
        "ops planner": "ship" if checks["ops: planner beats heuristic (95% interval above zero)"] else "hold: keep the heuristic",
        "pricing design": "switchback" if checks["pricing: switchback bias within 10% of the true effect"] else "none trusted",
        "pricing policy": "ship" if checks["pricing: policy uplift confirmed by switchback"]
        else "hold: run the switchback longer",
        "sensing model": "ship" if all(v for k, v in checks.items() if k.startswith("sensing")) else "hold",
    }
    out = {"checks": checks, "decisions": decisions}
    (R / "dev" / "gate.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
