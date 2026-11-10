# SPDX-License-Identifier: GPL-3.0-or-later
"""Fuzzy search used by the hub filter and the command palette."""

# (field, weight, allow subsequence matching). Fuzzy matching on long free text
# such as descriptions matches almost anything, so those fields need a substring.
_FIELD_WEIGHTS = (
    ("name", 1.0, True),
    ("id", 0.8, True),
    ("keywords", 0.8, False),
    ("category", 0.6, False),
    ("description", 0.4, False),
)
_RECENT_BONUS = 30.0


def score(query, text, fuzzy=True):
    """Score one query word against one text. None means no match; higher is better."""
    q = query.lower().strip()
    t = text.lower()
    if not q:
        return 0.0
    if not t:
        return None
    index = t.find(q)
    if index >= 0:
        value = 100.0 - index * 0.5
        if index == 0 or not t[index - 1].isalnum():
            value += 50.0  # starts a word
        if len(q) == len(t):
            value += 50.0  # exact
        return value
    if not fuzzy:
        return None
    # Subsequence match ("selin" -> "SELect INstances"), penalising gaps.
    position = -1
    gaps = 0
    word_starts = 0
    for ch in q:
        found = t.find(ch, position + 1)
        if found < 0:
            return None
        if position >= 0:
            gaps += found - position - 1
        if found == 0 or not t[found - 1].isalnum():
            word_starts += 1
        position = found
    return max(1.0, 50.0 - gaps * 1.5 + word_starts * 5.0)


def _fields(tool):
    return {
        "name": tool.name,
        "id": tool.id.replace("_", " "),
        "keywords": " ".join(tool.keywords),
        "category": tool.category,
        "description": tool.description,
    }


def score_tool(query, tool):
    """Every word in the query must match some field; returns None otherwise."""
    words = query.split()
    if not words:
        return 0.0
    fields = _fields(tool)
    total = 0.0
    for word in words:
        best = None
        for field_name, weight, fuzzy in _FIELD_WEIGHTS:
            s = score(word, fields[field_name], fuzzy=fuzzy)
            if s is not None:
                s *= weight
                if best is None or s > best:
                    best = s
        if best is None:
            return None
        total += best
    return total


def rank(query, tools, recent=()):
    """Matching tools, best first. With an empty query: recent tools first, then by name."""
    recent_index = {tool_id: i for i, tool_id in enumerate(recent)}
    if not query.strip():
        return sorted(
            tools,
            key=lambda t: (recent_index.get(t.id, len(recent_index)), t.name.lower()),
        )
    scored = []
    for tool in tools:
        s = score_tool(query, tool)
        if s is None:
            continue
        if tool.id in recent_index:
            s += _RECENT_BONUS / (1 + recent_index[tool.id])
        scored.append((s, tool))
    scored.sort(key=lambda pair: (-pair[0], pair[1].name.lower()))
    return [tool for _, tool in scored]
