export type Interval = { mean: number; lo: number; hi: number };

export type PolicyScore = {
  contribution_per_day: number;
  contribution_per_vehicle_day: number;
  rides_per_day: number;
  served_share: number;
  ops_per_day: { swap: number; move: number };
  vs_heuristic: Interval;
};

export type Ops = {
  city: string;
  fleet: number;
  zones: number;
  history_days: number;
  eval_days: number;
  seeds: number[];
  policies: Record<string, PolicyScore>;
  forecast: {
    naive: { wape_zone_6h: number; bias: number };
    corrected: { wape_zone_6h: number; bias: number };
    censoring: { observed_rides_share_of_demand: number; corrected_share_of_demand: number };
  };
};

export type Replication = { rep: number; truth: number; user_ab: number; switchback: number };
export type DesignScore = { bias: number; sd: number; rmse: number; sign_correct: number };
export type Validation = {
  true_uplift_per_day: number;
  true_uplift_relative: number;
  true_rides_change: number;
  switchback_estimate_per_day: number;
  per_seed: { true: number[]; switchback: number[] };
};

export type Pricing = {
  dev: {
    design: {
      replications: Replication[];
      test_multiplier: number;
      days: number;
      user_ab: DesignScore;
      switchback: DesignScore;
      truth: { mean: number; sd: number; relative: number };
    };
    policy: Record<string, number>;
    validation: Validation;
  } | null;
  heldout: { policy: Record<string, number>; validation: Validation } | null;
};

export type Did = { effect: number; lo: number; hi: number };
export type Causal = {
  event_day: number;
  treated_zones: number;
  truth: number;
  rides: { naive_pre_post: number; did: Did; event_study: { week: number; effect: number }[] };
  demand_corrected: { naive_pre_post: number; did: Did; event_study: { week: number; effect: number }[] };
};

export type Sensing = {
  split: string;
  hardware: string;
  slowdown_threshold: number;
  windows: {
    surface_macro_f1: number;
    sidewalk_precision: number;
    sidewalk_recall: number;
    tandem_auroc: number;
    tandem_precision?: number;
    tandem_recall?: number;
  };
  rides: { sidewalk_stretches: number; caught_share: number; median_seconds_to_catch: number | null; false_slowdowns_per_100km: number; legal_km: number };
  edge?: { params: number; int8_kb: number; int8_ms_per_window: number; int8_top1_agreement: number };
};

export type Hero = {
  date: string;
  grid: number;
  available: number[][];
  lost: number[][];
  rides: number[][];
  zone_type: number[];
  totals: { rides: number; lost_opens: number; fleet: number };
};

export type Summary = {
  generated: string;
  hero: Hero | null;
  ops: { dev: Ops | null; heldout: Ops | null };
  pricing: Pricing;
  causal: Causal | null;
  sensing: { dev: Sensing | null; heldout: Sensing | null };
  gate: { checks: Record<string, boolean>; decisions: Record<string, string> } | null;
};
