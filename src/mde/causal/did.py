"""Difference in differences with an event study, for a change the operator did not randomise.

Here: a competitor launched in the eastern third of the city in mid-June. Ride counts in those zones fell,
but June also differs from May for every zone. The comparison zones carry the common trend; the event study
shows whether treated and comparison zones moved together before the launch.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def did(panel: pd.DataFrame, y: str, n_boot: int = 500, seed: int = 0) -> dict:
    """panel: zone, day, treated (bool), post (bool), y. Two-way fixed effects on log(1 + y)."""
    p = panel.copy()
    p["ly"] = np.log1p(p[y])

    def estimate(df: pd.DataFrame) -> float:
        # within transformation for zone and day fixed effects, then OLS on treated x post
        r = df["ly"] - df.groupby("zone")["ly"].transform("mean") - df.groupby("day")["ly"].transform("mean") + df["ly"].mean()
        d = (df["treated"] & df["post"]).astype(float)
        dd = d - d.groupby(df["zone"]).transform("mean") - d.groupby(df["day"]).transform("mean") + d.mean()
        return float((dd * r).sum() / (dd * dd).sum())

    beta = estimate(p)
    rng = np.random.default_rng(seed)
    zones = p["zone"].unique()
    treated = p.groupby("zone")["treated"].first()
    tz, cz = zones[treated.loc[zones].to_numpy()], zones[~treated.loc[zones].to_numpy()]
    boots = []
    groups = {z: g for z, g in p.groupby("zone")}
    for _ in range(n_boot):
        pick = np.concatenate([rng.choice(tz, len(tz)), rng.choice(cz, len(cz))])
        df = pd.concat([groups[z].assign(zone=i) for i, z in enumerate(pick)])
        boots.append(estimate(df))
    lo, hi = np.quantile(boots, [0.025, 0.975])
    return {"effect": float(np.expm1(beta)), "lo": float(np.expm1(lo)), "hi": float(np.expm1(hi))}


def naive_pre_post(panel: pd.DataFrame, y: str) -> float:
    t = panel[panel["treated"]]
    return float(t.loc[t["post"], y].mean() / t.loc[~t["post"], y].mean() - 1)


def event_study(panel: pd.DataFrame, y: str, event_day: int) -> list[dict]:
    """Weekly treated-minus-comparison gap in log(1 + y), relative to the week before the event."""
    p = panel.copy()
    p["ly"] = np.log1p(p[y])
    p["week"] = (p["day"] - event_day) // 7
    g = p.groupby(["week", "treated"])["ly"].mean().unstack("treated")
    gap = g[True] - g[False]
    ref = gap.loc[-1]
    return [{"week": int(w), "effect": float(np.expm1(v - ref))} for w, v in gap.items()]
