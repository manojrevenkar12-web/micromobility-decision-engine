"""Score the held-out city and the held-out scooter hardware once.

Refuses to run if the held-out definition changed since it was pinned (config/heldout.lock) or if any
held-out report already exists. Everything it uses (models, thresholds, the price policy, settings) was
fixed on the dev city.

    python scripts/heldout.py --pin    # before anything is scored
    python scripts/heldout.py
"""

from __future__ import annotations

import hashlib
import sys

import ops_eval
import pricing_eval
import sensing_eval

from mde import config

LOCK = config.CONFIG / "heldout.lock"
FILES = [config.CONFIG / "world.toml", config.ROOT / "src" / "mde" / "world" / "imu.py"]
OUTPUTS = [config.REPORTS / "heldout" / "ops.json", config.REPORTS / "heldout" / "pricing.json",
           config.REPORTS / "sensing_heldout.json"]


def fingerprint() -> str:
    return " ".join(hashlib.sha256(f.read_bytes()).hexdigest() for f in FILES)


def main() -> None:
    if sys.argv[1:] == ["--pin"]:
        LOCK.write_text(fingerprint() + "\n")
        print("pinned")
        return
    if LOCK.read_text().strip() != fingerprint():
        sys.exit("the held-out definition changed since config/heldout.lock was pinned; refusing")
    if any(p.exists() for p in OUTPUTS):
        sys.exit("held-out reports exist: the held-out city and hardware are scored once")
    ops_eval.main("heldout")
    pricing_eval.main("heldout")
    sensing_eval.main("heldout")


if __name__ == "__main__":
    main()
