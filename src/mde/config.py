"""Paths and settings. Every number the code uses comes from config/*.toml."""

from __future__ import annotations

import tomllib
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config"
DATA = ROOT / "data"
REPORTS = ROOT / "reports"


@cache
def load(name: str) -> dict:
    with open(CONFIG / f"{name}.toml", "rb") as f:
        return tomllib.load(f)


def world() -> dict:
    return load("world")


def decide() -> dict:
    return load("decide")


def gate() -> dict:
    return load("gate")
