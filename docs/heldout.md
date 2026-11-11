# Held-out log

| Date | What ran | Result |
|---|---|---|
| 2026-11-11 | `make heldout`, first and only run: held-out city (fleet 1,100, other layout and demand) and gen7 scooters | Operations: censored planner −38 €/day, corrected +21 € (+11 to +33). Forecast WAPE 12.3% vs 35.9%. Weekend price +1.9% true uplift, switchback could not confirm. Sensing on gen7: sidewalk stretches caught 68% (dev 91%), 0 false slowdowns, two riders 92%/88% precision/recall. |

The sensing drop is the expected cost of a new scooter generation without recalibration: the stiffer mount
moves the deck's resonance, and the threshold set on gen6 is too strict for it (SKILLS.md).
