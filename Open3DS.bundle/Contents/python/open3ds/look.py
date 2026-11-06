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

ICON_SIZES = {"small": 24, "medium": 32, "large": 48}

# Fixed colors for the usual categories so they never clash; others are hashed.
KNOWN_CATEGORY_COLORS = {
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


def wrap_label(text, width, measure, max_lines=2):
    """Break text into at most max_lines lines no wider than width.

    measure(str) -> width in pixels. The last line is elided with an ellipsis if needed.
    """
    words = (text or "").split()
    if not words:
        return ""
    lines = []
    current = ""
    for index, word in enumerate(words):
        candidate = word if not current else current + " " + word
        if measure(candidate) <= width or not current:
            current = candidate
            continue
        lines.append(current)
        current = word
        if len(lines) == max_lines - 1:
            current = " ".join(words[index:])
            break
    lines.append(current)
    return "\n".join(_elide(line, width, measure) for line in lines[:max_lines])


def _elide(text, width, measure):
    if measure(text) <= width:
        return text
    ellipsis = "…"
    while text and measure(text + ellipsis) > width:
        text = text[:-1]
    return text.rstrip() + ellipsis
