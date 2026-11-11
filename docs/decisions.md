# Decisions

**Censored demand is corrected with app opens, not modelled away.** Opens that found no scooter are counted at the
conversion seen in the same zone and hour band when a scooter was near. People who saw no scooter and did not
open the app stay invisible, which is why the correction recovers about 96% and not 100%.

**The planner did not replace the heuristic.** Marginal-value planning on forecast demand and expected arrivals,
with lean crews (80 swaps and 130 moves a day for 1,100-1,200 scooters), matched the status quo on dev
(+11 € a day, interval −5 to +25) and was +21 € (+11 to +33) on the held-out city; a perfect forecast adds
+25-26 €. With censored data it loses 38-51 € a day. The bottleneck is crew capacity and the flow of
scooters with rides, not where the next move goes. Kept: the forecast, which ships.

**Switchback over rider A/B, but not on four weeks.** Rider-level randomisation understated a +20% price
effect by 25% in ten of ten replications (interference through shared scooters). The switchback was
unbiased (−2%) but its spread was 200 € a day. Two variance reductions were tried and dropped: adjusting for
scooters available at the start of an hour, and for app opens. Both are moved by the price earlier in the
same window (fewer rides leave more scooters; more scooters mean more people find one). Adjusting for opens
alone biased the estimate by −141 € a day on a 509 € effect (−28%); adding scooters available pulled the
first replications down by a similar amount.

**The weekend price policy is held.** The elasticity switchback chose 1.15× at weekends. Its true uplift is
+1.9% of contribution in both cities with 2% fewer rides, but a 34-day switchback on dev measured −177 € to
+284 € a day across three seeds (held-out, 62 days: −230 € to +22 €) and cannot confirm it.

**DiD on corrected demand, not rides.** Rides are capped by the fleet, so the competitor's −18% shows as −11%
in rides; corrected demand gives −16% (−19% to −13%). A simple before-and-after shows −0.5%: June growth hid it.

**Sidewalk threshold set on rides, not windows.** The scooter acts after three sidewalk windows in a row; the
threshold is the lowest that keeps false slowdowns at or below 1 per 100 km of legal riding on validation.
A fifth of sidewalks are smooth asphalt, which the IMU cannot tell from a road.
