import type { Summary } from "../shared/data/types";
import { useJson, type Fetcher } from "../shared/data/useJson";
import { ErrorNotice } from "../shared/ui/Notice";
import { Skeleton } from "../shared/ui/Skeleton";
import { color, measure, size, space, weight } from "../shared/theme/tokens";
import { fmt } from "../shared/format";
import { Causal } from "../features/causal/Causal";
import { Forecast } from "../features/forecast/Forecast";
import { Gate } from "../features/gate/Gate";
import { Ops } from "../features/ops/Ops";
import { Pricing } from "../features/pricing/Pricing";
import { Sensing } from "../features/sensing/Sensing";
import { StreetMap } from "../features/streets/StreetMap";

const URL = "./data/summary.json";
// Module-level so its identity is stable: a new function each render would refetch forever.
const browserFetch: Fetcher = (u) => fetch(u);

export function App({ fetcher = browserFetch }: { fetcher?: Fetcher }) {
  const load = useJson<Summary>(URL, fetcher);
  return (
    <main style={{ maxWidth: measure.page, margin: "0 auto", padding: `0 ${space[5]}px ${space[8]}px` }}>
      {load.state === "loading" && (
        <div style={{ paddingTop: space[8] }}>
          <Skeleton label="Loading results" rows={6} />
        </div>
      )}
      {load.state === "error" && (
        <div style={{ paddingTop: space[8] }}>
          <ErrorNotice message={load.message} onRetry={load.retry} />
        </div>
      )}
      {load.state === "ready" && <Dashboard summary={load.data} />}
    </main>
  );
}

export function Dashboard({ summary }: { summary: Summary }) {
  const ops = summary.ops.dev;
  return (
    <>
      <header style={{ padding: `${space[8]}px 0 ${space[7]}px`, display: "grid", gap: space[5] }}>
        <h1 style={{ fontSize: size.xxl, fontWeight: weight.bold, lineHeight: 1.08, letterSpacing: "-0.02em", margin: 0, maxWidth: "22ch" }}>
          A shared scooter fleet, and the rides nobody saw it lose
        </h1>
        <p style={{ color: color.muted, fontSize: size.lg, margin: 0, maxWidth: `${measure.text}ch` }}>
          A simulated city of {ops?.zones ?? 144} zones and {ops?.fleet.toLocaleString("en-GB") ?? "1,200"} scooters, with the true demand hidden from
          every model. {ops ? `The ride table showed ${fmt(ops.forecast.censoring.observed_rides_share_of_demand * 100, 0)}% of it.` : ""} Scrub through
          a July Wednesday: teal is scooters on the street, orange is people who opened the app and found none.
        </p>
        <StreetMap hero={summary.hero} />
      </header>
      <Forecast ops={ops} />
      <Ops dev={summary.ops.dev} heldout={summary.ops.heldout} decision={summary.gate?.decisions["ops planner"]} />
      <Pricing data={summary.pricing} />
      <Causal data={summary.causal} />
      <Sensing dev={summary.sensing.dev} heldout={summary.sensing.heldout} />
      <Gate gate={summary.gate} />
      <footer style={{ borderTop: `1px solid ${color.line}`, paddingTop: space[5], color: color.muted, fontSize: size.sm }}>
        Generated {summary.generated} from <code>reports/</code> by <code>make report</code>. Everything here is simulated; no Bolt data was used.
      </footer>
    </>
  );
}
