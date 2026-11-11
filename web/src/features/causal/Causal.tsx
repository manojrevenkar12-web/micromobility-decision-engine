import type { Causal as CausalData } from "../../shared/data/types";
import { fmt, signed } from "../../shared/format";
import { EmptyNotice } from "../../shared/ui/Notice";
import { Section } from "../../shared/ui/Section";
import { color, measure, size, space } from "../../shared/theme/tokens";

const W = 640;
const PAD = { l: measure.axis + space[3], r: 150, t: space[4], b: measure.axis };

export function Causal({ data }: { data: CausalData | null }) {
  return (
    <Section
      title="What did the competitor's launch cost?"
      lede="A competitor launched in the eastern third of the city in mid-June. Nobody randomised it, so the eastern zones are compared with the rest of the city before and after (difference in differences). June also brought more riders everywhere, which hides the loss in a simple before-and-after."
    >
      {!data ? (
        <EmptyNotice what="quasi-experiment" command="make causal && make report" />
      ) : (
        <div style={{ display: "grid", gap: space[5] }}>
          <EventStudy data={data} />
          <table style={{ borderCollapse: "collapse", fontVariantNumeric: "tabular-nums" }}>
            <thead>
              <tr style={{ color: color.muted, fontSize: size.sm, textAlign: "right" }}>
                <th style={{ textAlign: "left", padding: space[2] }}>Outcome</th>
                <th style={{ padding: space[2] }}>Before vs after</th>
                <th style={{ padding: space[2] }}>Difference in differences (95%)</th>
              </tr>
            </thead>
            <tbody>
              {(["rides", "demand_corrected"] as const).map((k) => (
                <tr key={k} style={{ borderTop: `1px solid ${color.line}`, textAlign: "right" }}>
                  <td style={{ textAlign: "left", padding: space[2] }}>{k === "rides" ? "Rides (censored)" : "Corrected demand"}</td>
                  <td style={{ padding: space[2] }}>{signed(data[k].naive_pre_post * 100, 1)}%</td>
                  <td style={{ padding: space[2] }}>
                    {signed(data[k].did.effect * 100, 1)}% ({fmt(data[k].did.lo * 100, 1)} to {fmt(data[k].did.hi * 100, 1)})
                  </td>
                </tr>
              ))}
              <tr style={{ borderTop: `1px solid ${color.line}`, textAlign: "right" }}>
                <td style={{ textAlign: "left", padding: space[2] }}>Truth in the simulator</td>
                <td />
                <td style={{ padding: space[2] }}>{signed(data.truth * 100, 0)}%</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </Section>
  );
}

function EventStudy({ data }: { data: CausalData }) {
  const series = [
    { key: "rides" as const, label: "Rides", tone: color.naive },
    { key: "demand_corrected" as const, label: "Corrected demand", tone: color.method },
  ];
  const weeks = data.rides.event_study.map((e) => e.week);
  const vals = series.flatMap((s) => data[s.key].event_study.map((e) => e.effect)).concat([data.truth, 0]);
  const lo = Math.min(...vals) - 0.03;
  const hi = Math.max(...vals) + 0.03;
  const H = measure.chart;
  const x = (w: number) => PAD.l + ((w - weeks[0]) / (weeks[weeks.length - 1] - weeks[0])) * (W - PAD.l - PAD.r);
  const y = (v: number) => PAD.t + ((hi - v) / (hi - lo)) * (H - PAD.t - PAD.b);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Weekly gap between eastern and other zones, relative to the week before the launch" style={{ width: "100%", height: "auto" }}>
      {[lo, 0, hi].map((t) => (
        <g key={t}>
          <line x1={PAD.l} x2={W - PAD.r} y1={y(t)} y2={y(t)} stroke={color.line} />
          <text x={PAD.l - space[2]} y={y(t) + 4} textAnchor="end" fontSize={size.xs} fill={color.muted}>{fmt(t * 100, 0)}%</text>
        </g>
      ))}
      <line x1={x(0) - 0.5 * (x(1) - x(0))} x2={x(0) - 0.5 * (x(1) - x(0))} y1={PAD.t} y2={H - PAD.b} stroke={color.ink} strokeDasharray="3 3" />
      <text x={x(0)} y={PAD.t + size.sm} fontSize={size.xs} fill={color.ink}>launch</text>
      <line x1={x(0)} x2={W - PAD.r} y1={y(data.truth)} y2={y(data.truth)} stroke={color.lost} strokeDasharray="5 4" />
      <text x={W - PAD.r + space[2]} y={y(data.truth) + 4} fontSize={size.xs} fill={color.lost}>truth {fmt(data.truth * 100, 0)}%</text>
      {series.map((s) => (
        <g key={s.key}>
          <polyline fill="none" stroke={s.tone} strokeWidth={2.5} points={data[s.key].event_study.map((e) => `${x(e.week)},${y(e.effect)}`).join(" ")} />
          <text x={W - PAD.r + space[2]} y={y(data[s.key].event_study[data[s.key].event_study.length - 1].effect) + 4} fontSize={size.xs} fill={s.tone}>
            {s.label}
          </text>
        </g>
      ))}
      {weeks.filter((w) => w % 2 === 0).map((w) => (
        <text key={w} x={x(w)} y={H - space[4]} textAnchor="middle" fontSize={size.xs} fill={color.muted}>{w > 0 ? `+${w}` : w} wk</text>
      ))}
    </svg>
  );
}
