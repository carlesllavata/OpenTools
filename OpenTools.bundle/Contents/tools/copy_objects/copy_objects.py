# SPDX-License-Identifier: GPL-3.0-or-later
"""Copy to the OpenTools clipboard; Shift / Ctrl / Alt pick the slot (see opentools.object_clipboard)."""

from opentools import object_clipboard


def run():
    object_clipboard.copy()