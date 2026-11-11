"""Paired comparisons with a moving-block bootstrap over days (weekly blocks keep weekday patterns)."""

from __future__ import annotations

import numpy as np


def block_bootstrap_ci(diff: np.ndarray, n_boot: int, block: int, seed: int = 0) -> dict:
    diff = np.asarray(diff, float)
    n = len(diff)
    rng = np.random.default_rng(seed)
    starts = np.arange(max(1, n - block + 1))
    means = []
    for _ in range(n_boot):
        idx = np.concatenate([np.arange(s, s + block) for s in rng.choice(starts, size=-(-n // block))])[:n]
        means.append(diff[idx % n].mean())
    return {"mean": float(diff.mean()), "lo": float(np.quantile(means, 0.025)), "hi": float(np.quantile(means, 0.975))}


def wape(pred: np.ndarray, truth: np.ndarray) -> float:
    return float(np.abs(pred - truth).sum() / np.abs(truth).sum())
