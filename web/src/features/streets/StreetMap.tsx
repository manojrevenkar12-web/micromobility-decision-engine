import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import type { Hero } from "../../shared/data/types";
import { EmptyNotice, buttonStyle } from "../../shared/ui/Notice";
import { color, measure, motion as m, size, space, weight } from "../../shared/theme/tokens";

const stockColour = (n: number) => color.stock[Math.min(color.stock.length - 1, n <= 0 ? 0 : Math.ceil(Math.log2(n + 1)))];

/** One weekday hour by hour: scooters rentable per zone (fill) and people who found none (orange dots). */
export function StreetMap({ hero }: { hero: Hero | null }) {
  const [hour, setHour] = useState(8);
  const [playing, setPlaying] = useState(false);
  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => setHour((h) => (h + 1) % 24), m.playMs);
    return () => clearInterval(id);
  }, [playing]);
  if (!hero) return <EmptyNotice what="street map" command="make report" />;
  const g = hero.grid;
  const cell = measure.map / g;
  const lostNow = hero.lost[hour].reduce((a, b) => a + b, 0);
  const ridesNow = hero.rides[hour].reduce((a, b) => a + b, 0);
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: space[6], alignItems: "flex-start" }}>
      <svg
        viewBox={`0 0 ${measure.map} ${measure.map}`}
        role="img"
        aria-label={`City grid at ${hour}:00: ${ridesNow} rides started, ${lostNow} people found no scooter`}
        style={{ width: "100%", maxWidth: measure.map, height: "auto", background: color.card }}
      >
        {hero.available[hour].map((n, z) => {
          const x = (z % g) * cell;
          const y = Math.floor(z / g) * cell;
          const lost = hero.lost[hour][z];
          return (
            <g key={z}>
              <rect x={x + measure.cellGap / 2} y={y + measure.cellGap / 2} width={cell - measure.cellGap} height={cell - measure.cellGap}
                fill={stockColour(n)} />
              <motion.circle cx={x + cell / 2} cy={y + cell / 2} fill={color.lost} fillOpacity={0.85}
                animate={{ r: lost ? Math.min(cell / 2 - 2, 3 + 4 * Math.sqrt(lost)) : 0 }}
                transition={{ duration: m.step, ease: m.ease }} />
            </g>
          );
        })}
      </svg>
      <div style={{ flex: "1 1 260px", display: "grid", gap: space[4] }}>
        <div>
          <div style={{ fontSize: size.xxl, fontWeight: weight.bold, fontVariantNumeric: "tabular-nums" }}>
            {String(hour).padStart(2, "0")}:00
          </div>
          <div style={{ color: color.muted }}>{new Date(hero.date).toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" })}</div>
        </div>
        <label style={{ display: "grid", gap: space[2] }}>
          <span style={{ fontWeight: weight.semibold }}>Hour</span>
          <input type="range" min={0} max={23} value={hour} onChange={(e) => setHour(Number(e.target.value))}
            style={{ accentColor: color.supply }} />
        </label>
        <button type="button" onClick={() => setPlaying((p) => !p)} aria-pressed={playing} style={buttonStyle}>
          {playing ? "Pause the day" : "Play the day"}
        </button>
        <dl style={{ margin: 0, display: "grid", gridTemplateColumns: "auto 1fr", gap: `${space[1]}px ${space[4]}px` }}>
          <dt style={{ color: color.muted }}>Rides started this hour</dt>
          <dd style={{ margin: 0, fontWeight: weight.semibold }}>{ridesNow}</dd>
          <dt style={{ color: color.lost }}>Found no scooter</dt>
          <dd style={{ margin: 0, fontWeight: weight.semibold }}>{lostNow}</dd>
          <dt style={{ color: color.muted }}>Whole day</dt>
          <dd style={{ margin: 0 }}>
            {hero.totals.rides.toLocaleString("en-GB")} rides, {hero.totals.lost_opens.toLocaleString("en-GB")} opens with no scooter
          </dd>
        </dl>
        <div aria-hidden style={{ display: "flex", alignItems: "center", gap: space[2], fontSize: size.xs, color: color.muted }}>
          <span>no scooters</span>
          {color.stock.map((c) => (
            <span key={c} style={{ width: space[5], height: space[3], background: c, border: `1px solid ${color.line}` }} />
          ))}
          <span>many</span>
        </div>
      </div>
    </div>
  );
}
