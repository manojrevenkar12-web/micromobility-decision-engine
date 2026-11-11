import type { Ops, Summary } from "../src/shared/data/types";

const ci = (m: number) => ({ mean: m, lo: m - 10, hi: m + 10 });
const policy = (c: number, d: number) => ({
  contribution_per_day: c, contribution_per_vehicle_day: c / 1200, rides_per_day: c / 4, rides_per_vehicle_day: 1,
  served_share: 0.75, ops_per_day: { swap: 80, move: 130 }, vs_heuristic: ci(d),
});
const ops: Ops = {
  city: "dev", fleet: 1200, zones: 4, history_days: 91, eval_days: 62, seeds: [1, 2, 3],
  policies: { heuristic: policy(4600, 0), "planner-naive": policy(4550, -50), "planner-corrected": policy(4610, 11), "planner-oracle": policy(4630, 26) },
  forecast: { naive: { wape_zone_6h: 0.35, bias: -0.23 }, corrected: { wape_zone_6h: 0.13, bias: 0.03 },
    censoring: { observed_rides_share_of_demand: 0.79, corrected_share_of_demand: 0.96 } },
};
const zeros = () => Array.from({ length: 24 }, () => [0, 1, 2, 3]);
const val = { true_uplift_per_day: 83, true_uplift_relative: 0.019, true_rides_change: -0.022, switchback_estimate_per_day: -7,
  per_seed: { true: [80, 85, 84], switchback: [-120, 280, -170] } };

export const fixture: Summary = {
  generated: "2026-11-11",
  hero: { date: "2025-07-02", grid: 2, available: zeros(), lost: zeros(), rides: zeros(), zone_type: [0, 1, 2, 2],
    totals: { rides: 100, lost_opens: 20, fleet: 1200 } },
  ops: { dev: ops, heldout: null },
  pricing: {
    dev: {
      design: { replications: [{ rep: 0, truth: 500, user_ab: 380, switchback: 520 }], test_multiplier: 1.2, days: 28,
        user_ab: { bias: -130, sd: 49, rmse: 136, sign_correct: 1 }, switchback: { bias: -10, sd: 200, rmse: 199, sign_correct: 1 },
        truth: { mean: 509, sd: 19, relative: 0.107 } },
      policy: { weekend: 1.15, weekday_peak: 1, weekday_offpeak: 1 },
      validation: val,
    },
    heldout: null,
  },
  causal: {
    event_day: 76, treated_zones: 48, truth: -0.18,
    rides: { naive_pre_post: -0.005, did: { effect: -0.114, lo: -0.15, hi: -0.07 }, event_study: [{ week: -1, effect: 0 }, { week: 0, effect: -0.1 }, { week: 1, effect: -0.12 }] },
    demand_corrected: { naive_pre_post: -0.03, did: { effect: -0.159, lo: -0.187, hi: -0.126 }, event_study: [{ week: -1, effect: 0 }, { week: 0, effect: -0.15 }, { week: 1, effect: -0.17 }] },
  },
  sensing: {
    dev: { split: "dev-test", hardware: "gen6", slowdown_threshold: 0.3,
      windows: { surface_macro_f1: 0.94, sidewalk_precision: 0.96, sidewalk_recall: 0.82, tandem_auroc: 0.98, tandem_precision: 0.9, tandem_recall: 0.9 },
      rides: { sidewalk_stretches: 476, caught_share: 0.91, median_seconds_to_catch: 6, false_slowdowns_per_100km: 0, legal_km: 272 },
      edge: { params: 45188, int8_kb: 56, int8_ms_per_window: 0.06, int8_top1_agreement: 0.998 } },
    heldout: null,
  },
  gate: { checks: { "forecast: |bias| <= 5%": true, "ops: planner beats heuristic (95% interval above zero)": false },
    decisions: { forecast: "ship", "ops planner": "hold: keep the heuristic" } },
};
