import type { Summary } from "../../shared/data/types";
import { EmptyNotice } from "../../shared/ui/Notice";
import { Section } from "../../shared/ui/Section";
import { color, space, weight } from "../../shared/theme/tokens";

export function Gate({ gate }: { gate: Summary["gate"] }) {
  return (
    <Section title="What ships" lede="Decided on the dev city by config/gate.toml before the held-out city was run. A held component stays held until its check passes; the bar is not moved.">
      {!gate ? (
        <EmptyNotice what="release decisions" command="make gate && make report" />
      ) : (
        <div style={{ display: "grid", gap: space[5], gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))" }}>
          <ul style={{ margin: 0, paddingLeft: space[5], display: "grid", gap: space[2] }}>
            {Object.entries(gate.decisions).map(([k, v]) => (
              <li key={k}>
                <span style={{ fontWeight: weight.semibold }}>{k}</span>: <span style={{ color: v.startsWith("hold") || v.startsWith("none") ? color.lost : color.good }}>{v}</span>
              </li>
            ))}
          </ul>
          <ul style={{ margin: 0, paddingLeft: space[5], display: "grid", gap: space[1], color: color.muted }}>
            {Object.entries(gate.checks).map(([k, ok]) => (
              <li key={k} style={{ color: ok ? color.ink : color.lost }}>{ok ? "Met" : "Not met"}: {k}</li>
            ))}
          </ul>
        </div>
      )}
    </Section>
  );
}
