"""Simulated scooter IMU windows: what the scooter's sensors record over 2 seconds of riding.

Surfaces excite the deck differently:
  road         asphalt: low broadband vibration, an occasional pothole; a quarter of roads are concrete
               slabs with a joint every 3-6 m
  sidewalk     paving slabs: an impulse at every joint, so a periodic train at speed / slab length,
               usually lower speeds and more braking (pedestrians), now and then a kerb drop; a fifth of
               sidewalks are smooth asphalt with no joints at all, which vibration alone cannot tell apart
  cobblestone  dense, strong impulses from stones 10-20 cm apart
The deck is a damped resonator tuned by the load: riders weigh 55-120 kg, a second rider adds 40-90 kg,
so a heavy rider alone and two light riders overlap. Two hardware generations differ in mount stiffness and
sensor noise.

This is hidden truth: labels come from here and nothing in mde.sensing reads it, except through the
data it returns.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import lfilter

SURFACES = ["road", "sidewalk", "cobblestone"]
FS = 100          # Hz
WINDOW = 200      # 2 s


@dataclass(frozen=True)
class Hardware:
    name: str
    resonance_hz: float      # single rider
    noise: float             # accelerometer noise, m/s^2
    gain: float              # mount transfer


HARDWARE = {
    "gen6": Hardware("gen6", 9.0, 0.08, 1.0),
    "gen7": Hardware("gen7", 10.5, 0.12, 0.85),   # held out: never in training
}


@dataclass(frozen=True)
class CityRoads:
    name: str
    slab_m: tuple[float, float]       # paving-slab length range
    cobble_m: tuple[float, float]
    road_roughness: float


CITIES = {
    "dev": CityRoads("dev", (0.30, 0.60), (0.10, 0.18), 0.22),
    "heldout": CityRoads("heldout", (0.25, 0.80), (0.08, 0.22), 0.30),
}


def _resonator(x: np.ndarray, f0: float, zeta: float) -> np.ndarray:
    w = 2 * np.pi * f0 / FS
    r = np.exp(-zeta * w)
    a = [1, -2 * r * np.cos(w * np.sqrt(max(1e-6, 1 - zeta**2))), r * r]
    b = [1 - r]
    return lfilter(b, a, x)


def window(surface: int, tandem: bool, hw: Hardware, roads: CityRoads, rng: np.random.Generator) -> np.ndarray:
    """One (5, WINDOW) window: vertical, longitudinal, lateral acceleration, pitch rate, speed."""
    n = WINDOW + 100  # 1 s of lead-in so the resonator has settled
    speed = rng.uniform(6, 20) if surface == 1 else rng.uniform(8, 25)
    mass = rng.uniform(55, 120) + (rng.uniform(40, 90) if tandem else 0.0) + 25.0   # riders + scooter, kg
    load = mass / 100.0
    accel = rng.normal(0, 0.25 if surface != 1 else 0.40) / load
    v = np.clip(speed / 3.6 + accel * np.arange(n) / FS + np.cumsum(rng.normal(0, 0.01, n)), 0.8, None)
    dist = np.cumsum(v) / FS
    ex = rng.normal(0, roads.road_roughness * (0.6 + v / 8), n)
    if surface == 0:
        for _ in range(rng.poisson(0.3)):
            ex[rng.integers(0, n)] += rng.uniform(3, 6)
        if rng.random() < 0.25:   # concrete slab road
            slab = rng.uniform(3.0, 6.0)
            joints = np.floor(dist / slab)
            ex += (np.diff(joints, prepend=joints[0]) > 0) * rng.uniform(1.5, 3.0)
    elif surface == 1 and rng.random() < 0.2:   # smooth asphalt sidewalk
        ex *= 0.8
    elif surface == 1:
        slab = rng.uniform(*roads.slab_m)
        joints = np.floor(dist / slab)
        hit = np.diff(joints, prepend=joints[0]) > 0
        ex += hit * rng.uniform(1.5, 3.0, n) * (0.7 + 0.3 * rng.random(n))
        ex *= 0.8
        if rng.random() < 0.15:
            ex[rng.integers(0, n)] -= rng.uniform(6, 10)  # kerb drop
    else:
        stone = rng.uniform(*roads.cobble_m)
        joints = np.floor(dist / stone)
        hit = np.diff(joints, prepend=joints[0]) > 0
        ex += hit * rng.uniform(1.0, 4.0, n) + rng.normal(0, 0.6, n)
    f0 = hw.resonance_hz * np.sqrt(1.45 / load) * rng.uniform(0.93, 1.07)
    zeta = 0.10 + 0.04 * load
    az = hw.gain * _resonator(ex, f0, zeta) / np.sqrt(load)
    ax = np.gradient(v) * FS + 0.3 * az + rng.normal(0, 0.05, n)
    ay = rng.normal(0, 0.15, n) + 0.2 * az * rng.uniform(-1, 1)
    gy = np.gradient(az) * 0.02 + 0.03 * (load - 1.4) + rng.normal(0, 0.01, n)
    x = np.stack([az, ax, ay, gy, v * 3.6])[:, -WINDOW:]
    x[:3] += rng.normal(0, hw.noise, (3, WINDOW))
    return x.astype(np.float32)


def dataset(n: int, hw: str, city: str, seed: int, sidewalk_share: float = 0.3) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """n windows -> X (n, 5, WINDOW), surface labels, tandem labels."""
    rng = np.random.default_rng(seed)
    p = np.array([1 - sidewalk_share - 0.15, sidewalk_share, 0.15])
    surf = rng.choice(3, size=n, p=p)
    tandem = rng.random(n) < 0.12
    X = np.stack([window(int(s), bool(t), HARDWARE[hw], CITIES[city], rng) for s, t in zip(surf, tandem, strict=True)])
    return X, surf.astype(np.int64), tandem.astype(np.int64)
