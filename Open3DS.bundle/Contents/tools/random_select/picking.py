"""Pure helpers for Random Select (no 3ds Max imports, so the offline tests can load them)."""

import random as _random


def clean_percent(value, default=30):
    """A whole percentage between 1 and 100."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number != number:  # NaN
        return default
    return max(1, min(100, int(round(number))))


def keep_count(total, percent):
    """How many of `total` items `percent` keeps: rounded half up, at least one when there is
    anything to pick (3 objects at 10% still keep one), never more than `total`."""
    if total <= 0:
        return 0
    count = int(total * clean_percent(percent) / 100.0 + 0.5)
    return max(1, min(total, count))


def pick(items, percent, rng=None):
    """A random subset of `items` holding `keep_count` of them, in their original order."""
    items = list(items)
    count = keep_count(len(items), percent)
    chosen = set((rng or _random).sample(range(len(items)), count))
    return [item for index, item in enumerate(items) if index in chosen]
