import { useState } from "react";
import type { Ops as OpsData } from "../../shared/data/types";
import { fmt, signed } from "../../shared/format";
import { EmptyNotice } from "../../shared/ui/Notice";
import { Section } from "../../shared/ui/Section";
import { Segmented } from "../../shared/ui/Segmented";
import { color, size, space, weight } from "../../shared/theme/tokens";

const LABEL: Record<string, string> = {
  heuristic: "Status quo: emptiest batteries, last fortnight's ride starts",
  "planner-naive": "Planner on the ride table (censored)",
  "planner-corrected": "Planner on corrected demand",
  "planner-oracle": "Planner with perfect demand (reference)",
};

type Split = "heldout" | "dev";

export function Ops({ dev, heldout, decision }: { dev: OpsData | null; heldout: OpsData | null; decision?: string }) {
  const [split, setSplit] = useState<Split>(heldout ? "heldout" : "dev");
  const o = split === "heldout" ? heldout : dev;
  return (
    <Section
      title="Where to put the scooters and which batteries to swap"
      lede="Each policy runs July and August with the same people, the same crews (80 swaps and 130 moves a day) and the same starting fleet. Bars: contribution per day against the status quo, with a 95% interval over days."
      aside={
        <Segmented label="City" value={split} onChange={setSplit}
          options={[{ value: "heldout", label: "Held-out city" }, { value: "dev", label: "Dev city" }]} />
      }
    >
      {!o ? (
        <EmptyNotice what={`${split} operations results`} command="make ops && make report" />
      ) : (
        <div style={{ display: "grid", gap: space[5] }}>
          <Intervals o={o} />
          {decision && (
            <p style={{ margin: 0, maxWidth: "66ch" }}>
              <b>Decision on dev: {decision}.</b> The planner on censored data loses money in both cities. On corrected demand its
              dev-city interval crossed zero, and even a perfect forecast adds under 1% at this crew size: crews, not placement, bind.
            </p>
          )}
        </div>
      )}
    </Section>
  );
}

function Intervals({ o }: { o: OpsData }) {
  const names = Object.keys(o.policies).filter((k) => k !== "heuristic");
  const ext = Math.max(...names.flatMap((k) => [Math.abs(o.policies[k].vs_heuristic.lo), Math.abs(o.policies[k].vs_heuristic.hi)])) * 1.2;
  const x = (v: number) => 50 + (v / ext) * 50;
  const base = o.policies.heuristic;
  return (
    <div style={{ display: "grid", gap: space[4] }}>
      <p style={{ margin: 0, color: color.muted, fontSize: size.sm }}>
        Status quo: {fmt(base.contribution_per_day, 0)} € a day, {fmt(base.rides_per_day, 0)} rides, {fmt(base.served_share * 100, 1)}% of true demand served.
      </p>
      {names.map((k) => {
        const c = o.policies[k].vs_heuristic;
        const tone = c.lo > 0 ? color.good : c.hi < 0 ? color.bad : color.method;
        return (
          <div key={k}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: space[3], flexWrap: "wrap" }}>
              <span style={{ fontWeight: weight.medium }}>{LABEL[k] ?? k}</span>
              <span style={{ fontVariantNumeric: "tabular-nums", color: tone }}>
                {signed(c.mean, 0)} € / day ({signed(c.lo, 0)} to {signed(c.hi, 0)})
              </span>
            </div>
            <svg viewBox="0 0 100 6" preserveAspectRatio="none" aria-hidden style={{ width: "100%", height: space[4], display: "block" }}>
              <rect x={0} y={2.5} width={100} height={1} fill={color.panel} />
              <rect x={49.9} y={0} width={0.2} height={6} fill={color.ink} />
              <rect x={x(c.lo)} y={2} width={Math.max(0.3, x(c.hi) - x(c.lo))} height={2} fill={tone} />
              <rect x={x(c.mean) - 0.4} y={0.5} width={0.8} height={5} fill={tone} />
            </svg>
          </div>
        );
      })}
    </div>
  );
}
