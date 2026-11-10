# SPDX-License-Identifier: GPL-3.0-or-later
"""Next Clipboard Target (see opentools.object_clipboard)."""

from opentools import object_clipboard


def run():
    object_clipboard.cycle_target()
