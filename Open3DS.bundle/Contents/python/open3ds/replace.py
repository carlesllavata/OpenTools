"""Weighted random replacement (pure Python, tested offline).

Ignite's Replace Objects turns each selected object into a copy or instance of one of
several source objects. Each source has a whole-number weight: a source with weight
40 is picked about 40/(sum of weights) of the time; weight 0 never.
"""

import random

DEFAULT_WEIGHT = 100
MAX_WEIGHT = 10000


def clean_weight(value):
    """A weight as an int in 0..MAX_WEIGHT (bad values give the default)."""
    if isinstance(value, bool):
        return DEFAULT_WEIGHT
    try:
        weight = int(round(float(value)))
    except (TypeError, ValueError):
        return DEFAULT_WEIGHT
    return max(0, min(MAX_WEIGHT, weight))


def pick(weights, count, rng=None):
    """`count` source indices (0-based) drawn by weight. Raises ValueError when no
    source has a weight above 0."""
    weights = [clean_weight(w) for w in weights]
    if not any(weights):
        raise ValueError("every source has weight 0")
    rng = rng or random.Random()
    return rng.choices(range(len(weights)), weights=weights, k=int(count))


def share(weights):
    """Expected share of each source, in percent (for the UI)."""
    weights = [clean_weight(w) for w in weights]
    total = sum(weights)
    return [(100.0 * w / total) if total else 0.0 for w in weights]
