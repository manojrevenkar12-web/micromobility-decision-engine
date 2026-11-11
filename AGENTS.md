# AGENTS.md

How to work in this repository, for people and coding agents.

## Fast feedback

- `make test` (13 tests, seconds) and `make lint`; `cd web && npm test`. CI runs all three.
- The full pipeline (`make ops pricing causal sensing gate report`) takes about 20 minutes on two cores.

## Invariants

1. **Decision code never reads the truth.** `src/mde/world` is the simulated world (true demand, price
   sensitivity, road surfaces). `demand`, `ops`, `pricing`, `causal` and `sensing` see only the logs the
   simulator writes. `tests/test_world_and_decisions.py` fails if they import the world or read its config.
   Only `mde.evals` and the evaluation scripts may read the truth, to score.
2. **Same people, different decisions.** Policies and prices are compared with common random numbers:
   the same seed gives the same intents, so a difference is the decision's, not luck's.
3. **Paired intervals.** Every comparison of two policies is paired by day with a block bootstrap.
4. **The gate is not moved.** `config/gate.toml` decides what ships on the dev city; a held component stays held.
5. **Settings in config.** Every number lives in `config/*.toml`.
6. **Generated reports.** `reports/`, `web/public/data/summary.json` and the README tables come from scripts.

## The held-out rule

The held-out city (another layout, fleet and demand) and the held-out scooter generation (gen7) are scored
once by `make heldout`, with everything fixed on dev. The script refuses if `config/heldout.lock` no longer
matches or if a held-out report exists. See `docs/heldout.md`.
