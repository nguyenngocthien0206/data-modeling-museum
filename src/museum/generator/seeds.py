"""Deterministic random streams.

Every stream is derived from (profile seed, stream name, extra keys such as a day index),
so a given day of a given table always gets the same numbers, whatever ran before it.
"""

from __future__ import annotations

import zlib

import numpy as np


def stream(seed: int, name: str, *keys: int) -> np.random.Generator:
    entropy = [seed, zlib.crc32(name.encode("utf-8")), *keys]
    return np.random.default_rng(np.random.SeedSequence(entropy))


def int_seed(seed: int, name: str, *keys: int) -> int:
    """A plain integer seed for libraries that do not take a numpy generator (Faker)."""
    return int(stream(seed, name, *keys).integers(0, 2**31 - 1))
