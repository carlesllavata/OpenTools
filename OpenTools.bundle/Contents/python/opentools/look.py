# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure helpers for how tools look in the hub: badge colors, initials and tile labels.

No Qt imports, so it can be tested outside 3ds Max.
"""

import re
import zlib

# Mid-tone colors that read well on both the dark and the light 3ds Max theme.
PALETTE = (
    "#d9534f",  # red
    "#e08a2c",  # orange
    "#c7a516",  # yellow
    "#5ba84f",  # green
    "#2fa395",  # teal
    "#3f8fe0",  # blue
    "#6f6fdb",  # indigo
    "#a862d6",  # purple
    "#d35f9e",  # pink
    "#7d8b96",  # slate
)

ICON_SIZES = {"small": 16, "medium": 20, "large": 24}

# Fixed colors for the usual categories so they never clash; others are hashed.
KNOWN_CATEGORY_COLORS = {
    "clipboard": "#4fb0c6",
    "modeling": "#3f8fe0",
    "modelling": "#3f8fe0",
    "materials": "#e08a2c",
    "lighting": "#c7a516",
    "render": "#d9534f",
    "rendering": "#d9534f",
    "scene": "#2fa395",
    "selection": "#5ba84f",
    "animation": "#d35f9e",
    "camera": "#6f6fdb",
    "cameras": "#6f6fdb",
    "files": "#a862d6",
    "utilities": "#7d8b96",
    "general": "#7d8b96",
}


def category_color(category):
    """Stable color for a category name (same name, same color, on every machine)."""
    key = (category or "").strip().lower()
    if key in KNOWN_CATEGORY_COLORS:
        return KNOWN_CATEGORY_COLORS[key]
    return PALETTE[zlib.crc32(key.encode("utf-8")) % len(PALETTE)]


def initials(name):
    """'Select Instances' -> 'SI', 'Unwrap' -> 'Un', 'UVW 2 Box' -> 'U2'."""
    words = re.findall(r"[^\W_]+", name or "")
    if not words:
        return "?"
    if len(words) == 1:
        word = words[0]
        return (word[0].upper() + word[1:2].lower()) if len(word) > 1 else word.upper()
    return (words[0][0] + words[1][0]).upper()
