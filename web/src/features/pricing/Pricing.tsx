import type { Pricing as PricingData } from "../../shared/data/types";
import { fmt, signed } from "../../shared/format";
import { EmptyNotice } from "../../shared/ui/Notice";
import { Section } from "../../shared/ui/Section";
import { color, measure, size, space, weight } from "../../shared/theme/tokens";

const W = 640;
const ROWS = [
  { key: "truth", label: "Truth (everyone at each price)", tone: color.truth },
  { key: "user_ab", label: "Rider-level A/B test", tone: color.naive },
  { key: "switchback", label: "City-wide switchback", tone: color.method },
] as const;

export function Pricing({ data }: { data: PricingData }) {
  const d = data.dev;
  return (
    <Section
      title="Testing a price on a shared fleet"
      lede="Riders in a price test share the same scooters. When the test group rides less, the control group finds more scooters, so a rider-level A/B test understates what a city-wide price change does. Each dot is one four-week experiment; the truth comes from running the same people under each price."
    >
      {!d ? (
        <EmptyNotice what="price experiments" command="make pricing && make report" />
      ) : (
        <div style={{ display: "grid", gap: space[6] }}>
          <Dots d={d.design} />
          <dl style={{ margin: 0, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: space[5] }}>
            <Fact value={`${signed(d.design.user_ab.bias, 0)} €`} label={`A/B bias per day (${fmt((d.design.user_ab.bias / d.design.truth.mean) * 100, 0)}% of the effect), spread ${fmt(d.design.user_ab.sd, 0)} €`} />
            <Fact value={`${signed(d.design.switchback.bias, 0)} €`} label={`switchback bias per day, but spread ${fmt(d.design.switchback.sd, 0)} €: four weeks is too short`} />
            <Fact value={`${signed(d.validation.true_uplift_relative * 100, 1)}%`}
              label={`true uplift of the chosen policy (weekend ×${d.policy.weekend}), rides ${signed(d.validation.true_rides_change * 100, 1)}%`} />
            {data.heldout && (
              <Fact value={`${signed(data.heldout.validation.true_uplift_relative * 100, 1)}%`} label="same policy, held-out city, true uplift" />
            )}
          </dl>
          <p style={{ margin: 0, maxWidth: "66ch" }}>
            The switchback that should confirm the policy measured {d.validation.per_seed.switchback.map((v) => `${signed(v, 0)} €`).join(", ")} per day
            on three runs whose true uplift was about {signed(d.validation.true_uplift_per_day, 0)} €. The policy is held until a longer test
            can tell a gain of this size from noise.
          </p>
        </div>
      )}
    </Section>
  );
}

function Dots({ d }: { d: NonNullable<PricingData["dev"]>["design"] }) {
  const vals = d.replications.flatMap((r) => [r.truth, r.user_ab, r.switchback]);
  const lo = Math.min(0, ...vals);
  const hi = Math.max(...vals) * 1.05;
  const pad = { l: 230, r: space[5] };
  const rowH = space[7];
  const H = rowH * ROWS.length + measure.axis;
  const x = (v: number) => pad.l + ((v - lo) / (hi - lo)) * (W - pad.l - pad.r);
  const ticks = [0, Math.round(hi / 2 / 100) * 100, Math.round(hi / 100) * 100].filter((t) => t <= hi);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Estimated effect of a 20% price rise per experiment, by design, against the truth" style={{ width: "100%", height: "auto" }}>
      {ticks.map((t) => (
        <g key={t}>
          <line x1={x(t)} x2={x(t)} y1={0} y2={H - measure.axis + space[2]} stroke={color.line} />
          <text x={x(t)} y={H - space[4]} textAnchor="middle" fontSize={size.xs} fill={color.muted}>{signed(t, 0)} € / day</text>
        </g>
      ))}
      {ROWS.map((r, i) => (
        <g key={r.key}>
          <text x={0} y={i * rowH + rowH / 2 + 4} fontSize={size.sm} fontWeight={weight.medium} fill={color.ink}>{r.label}</text>
          {d.replications.map((rep) => (
            <circle key={rep.rep} cx={x(rep[r.key])} cy={i * rowH + rowH / 2} r={measure.dot - 1} fill={r.tone} fillOpacity={0.7} />
          ))}
        </g>
      ))}
    </svg>
  );
}

export function Fact({ value, label }: { value: string; label: string }) {
  return (
    <div style={{ borderTop: `3px solid ${color.supply}`, paddingTop: space[3] }}>
      <dd style={{ margin: 0, fontSize: size.xl, fontWeight: weight.bold, fontVariantNumeric: "tabular-nums" }}>{value}</dd>
      <dt style={{ color: color.muted, fontSize: size.sm }}>{label}</dt>
    </div>
  );
}
