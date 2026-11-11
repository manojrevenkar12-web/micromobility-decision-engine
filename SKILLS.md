# SKILLS.md

## Try a new operations policy
Implement `plan(obs) -> Plan` in `src/mde/ops/policies.py` using only the `Observation` and its logs, add it to
`policies` in `scripts/ops_eval.py`, run `make ops gate report`. It is compared with the status quo on the same
people, paired by day.

## Test a price change
Use `switchback_assign` and `estimate_switchback` (`src/mde/pricing/experiments.py`). Do not adjust for app opens
or scooters available: the price moves both (docs/decisions.md). Budget enough weeks: four weeks gave a
spread of about 200 € a day on a 500 € effect.

## Read a change nobody randomised
Build a zone-by-day panel, mark treated zones and the event date, run `mde.causal.did` on corrected demand
(not rides, which the fleet caps), and check the event study's pre-period is flat.

## Retune the sidewalk model for a new scooter generation
Record labelled rides on the new hardware, rerun `scripts/sensing_eval.py dev` with them in validation, and pick
the slowdown threshold again. The held-out gen7 result shows what happens without this step.
