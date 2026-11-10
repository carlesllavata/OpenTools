# SPDX-License-Identifier: GPL-3.0-or-later
"""Paste on Cursor (see opentools.object_clipboard)."""

from opentools import object_clipboard


def run():
    object_clipboard.paste(how="cursor")
