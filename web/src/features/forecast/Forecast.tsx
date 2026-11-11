import type { Ops } from "../../shared/data/types";
import { fmt } from "../../shared/format";
import { EmptyNotice } from "../../shared/ui/Notice";
import { Section } from "../../shared/ui/Section";
import { color, size, space, weight } from "../../shared/theme/tokens";

const pct = (v: number, d = 0) => `${fmt(v * 100, d)}%`;

export function Forecast({ ops }: { ops: Ops | null }) {
  return (
    <Section
      title="Rides you never saw are demand too"
      lede="When no scooter is near, the ride never happens and never reaches the ride table. A forecast trained on rides learns the shortage, not the demand. App opens that found nothing put the missing rides back."
    >
      {!ops ? (
        <EmptyNotice what="forecast scores" command="make ops && make report" />
      ) : (
        <div style={{ display: "grid", gap: space[6], gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))" }}>
          <Bars
            title="Share of true demand each source sees (history)"
            rows={[
              { label: "Rides in the ride table", value: ops.forecast.censoring.observed_rides_share_of_demand, tone: color.naive },
              { label: "Rides plus opens that found nothing", value: ops.forecast.censoring.corrected_share_of_demand, tone: color.method },
            ]}
            max={1}
            format={(v) => pct(v)}
          />
          <Bars
            title="Forecast error, zone by 6 hours, July-August (WAPE)"
            rows={[
              { label: `Trained on rides (bias ${pct(ops.forecast.naive.bias)})`, value: ops.forecast.naive.wape_zone_6h, tone: color.naive },
              { label: `Trained on corrected demand (bias ${pct(ops.forecast.corrected.bias, 1)})`, value: ops.forecast.corrected.wape_zone_6h, tone: color.method },
            ]}
            max={Math.max(ops.forecast.naive.wape_zone_6h, ops.forecast.corrected.wape_zone_6h) * 1.1}
            format={(v) => pct(v, 1)}
          />
        </div>
      )}
    </Section>
  );
}

function Bars({ title, rows, max, format }: { title: string; rows: { label: string; value: number; tone: string }[]; max: number; format: (v: number) => string }) {
  return (
    <div>
      <h3 style={{ margin: `0 0 ${space[3]}px`, fontSize: size.md, fontWeight: weight.semibold }}>{title}</h3>
      <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: space[3] }}>
        {rows.map((r) => (
          <li key={r.label}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: space[3] }}>
              <span>{r.label}</span>
              <b style={{ fontVariantNumeric: "tabular-nums" }}>{format(r.value)}</b>
            </div>
            <div aria-hidden style={{ height: space[3], background: color.panel, marginTop: space[1] }}>
              <div style={{ width: `${(r.value / max) * 100}%`, height: "100%", background: r.tone }} />
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
