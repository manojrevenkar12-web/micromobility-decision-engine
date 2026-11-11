import type { Sensing as SensingData } from "../../shared/data/types";
import { fmt } from "../../shared/format";
import { EmptyNotice } from "../../shared/ui/Notice";
import { Section } from "../../shared/ui/Section";
import { color, size, space, weight } from "../../shared/theme/tokens";

export function Sensing({ dev, heldout }: { dev: SensingData | null; heldout: SensingData | null }) {
  return (
    <Section
      title="Sidewalk riding and two people on one scooter, from the deck's IMU"
      lede="A 45k-parameter 1-D CNN reads 2 seconds of accelerometer, gyro and speed. The scooter warns and slows down after three sidewalk windows in a row. The threshold was set on validation rides so that riding on the road almost never triggers a slowdown; the held-out column is a scooter generation and a city the model never saw."
    >
      {!dev ? (
        <EmptyNotice what="sensing results" command="make sensing && make report" />
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table style={{ borderCollapse: "collapse", width: "100%", fontVariantNumeric: "tabular-nums" }}>
            <thead>
              <tr style={{ color: color.muted, fontSize: size.sm, textAlign: "right" }}>
                <th style={{ textAlign: "left", padding: space[2] }}>Measure</th>
                <th style={{ padding: space[2] }}>Dev-test, {dev.hardware}</th>
                <th style={{ padding: space[2] }}>Held-out, {heldout?.hardware ?? "—"}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(([label, get]) => (
                <tr key={label} style={{ borderTop: `1px solid ${color.line}`, textAlign: "right" }}>
                  <td style={{ textAlign: "left", padding: space[2], fontWeight: weight.medium }}>{label}</td>
                  <td style={{ padding: space[2] }}>{get(dev)}</td>
                  <td style={{ padding: space[2] }}>{heldout ? get(heldout) : "not scored yet"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {dev.edge && (
            <p style={{ color: color.muted, fontSize: size.sm }}>
              On the scooter: int8 ONNX, {fmt(dev.edge.int8_kb, 0)} kB, {fmt(dev.edge.int8_ms_per_window, 2)} ms per 2-second window on one CPU thread,
              {` ${fmt(dev.edge.int8_top1_agreement * 100, 1)}%`} of windows classified the same as the float model.
            </p>
          )}
        </div>
      )}
    </Section>
  );
}

const pct = (v: number | undefined) => (v === undefined ? "—" : `${fmt(v * 100, 1)}%`);
const rows: [string, (s: SensingData) => string][] = [
  ["Sidewalk stretches caught (10 s or longer)", (s) => pct(s.rides.caught_share)],
  ["Median time to slow down", (s) => (s.rides.median_seconds_to_catch === null ? "—" : `${fmt(s.rides.median_seconds_to_catch, 0)} s`)],
  ["False slowdowns per 100 km of legal riding", (s) => fmt(s.rides.false_slowdowns_per_100km, 2)],
  ["Sidewalk window precision / recall", (s) => `${pct(s.windows.sidewalk_precision)} / ${pct(s.windows.sidewalk_recall)}`],
  ["Surface macro F1 (road, sidewalk, cobblestone)", (s) => fmt(s.windows.surface_macro_f1, 3)],
  ["Two riders: precision / recall", (s) => `${pct(s.windows.tandem_precision)} / ${pct(s.windows.tandem_recall)}`],
];
